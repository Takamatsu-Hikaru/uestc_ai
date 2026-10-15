"""Verification mail delivery.

Two providers are supported and selected from the admin console:

* ``resend`` — HTTPS API, no egress beyond 443.
* ``smtp``   — any relay (Aliyun DirectMail, for example) over implicit TLS
  (465) or STARTTLS (587/80/25).

Provider secrets are encrypted with ``MAIL_ENCRYPTION_KEY`` (falling back to the
AI gateway key) and never leave the database in clear text. Until an admin saves
a configuration the platform keeps using the ``RESEND_*`` environment values.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from .extensions import db
from .mail_models import PROVIDERS, SMTP_SECURITIES, MailSettings
from .models import iso, utcnow

DEFAULT_SENDER = "UESTC AI <noreply@example.com>"
DEFAULT_TIMEOUT = 12
ADDRESS_PATTERN = re.compile(r"^[^@\s,;]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,198}[A-Za-z0-9])?$")
SMTP_FIELDS = ("smtp_host", "smtp_port", "smtp_security", "smtp_username", "smtp_secret")


def _clip(value, limit: int = 200) -> str:
    return " ".join(str(value or "").split())[:limit]


class MailDeliveryError(RuntimeError):
    """Carries a stable message for the API plus an operator-facing detail."""

    def __init__(self, message: str, *, provider: str = "", detail: str = ""):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.detail = _clip(detail)


def verification_email_html(code: str, purpose: str = "register") -> str:
    digits = "".join(f'<span style="display:inline-block;min-width:28px">{digit}</span>' for digit in code)
    action = "重置账户密码" if purpose == "reset" else "完成平台注册"
    return f"""<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;background:#f2f0ea;color:#262723;font-family:Arial,'Microsoft YaHei',sans-serif">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 16px">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#fff;border-top:4px solid #c95d43">
          <tr><td style="padding:30px 34px 14px">
            <div style="font-size:12px;letter-spacing:2px;color:#6c6e67">UESTC AI</div>
            <h1 style="margin:18px 0 8px;font-family:Georgia,'Noto Serif SC',serif;font-size:27px;font-weight:400">验证你的邮箱</h1>
            <p style="margin:0;color:#686a64;font-size:14px;line-height:1.8">使用下面的验证码{action}。验证码在 10 分钟内有效。</p>
          </td></tr>
          <tr><td style="padding:18px 34px">
            <div style="border:1px solid #d7d3ca;background:#f5f3ee;padding:18px 16px;text-align:center;font-family:Consolas,monospace;font-size:30px;letter-spacing:6px;color:#262723">{digits}</div>
          </td></tr>
          <tr><td style="padding:8px 34px 30px">
            <p style="margin:0;color:#7b7d76;font-size:12px;line-height:1.8">如果不是你本人发起，请忽略这封邮件。请勿向任何人提供验证码，平台工作人员不会索要验证码。</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def send_verification_email(email: str, code: str, purpose: str = "register") -> None:
    if current_app.testing:
        return
    action = "密码找回" if purpose == "reset" else "注册"
    subject = "UESTC AI 密码找回验证码" if purpose == "reset" else "UESTC AI 邮箱验证码"
    text = f"你的 UESTC AI {action}验证码是：{code}\n\n验证码在 10 分钟内有效。请勿向任何人提供验证码。"
    send_mail(email, subject, text, verification_email_html(code, purpose))


def cipher() -> Fernet:
    secret = (current_app.config.get("MAIL_ENCRYPTION_KEY")
              or current_app.config.get("AI_GATEWAY_ENCRYPTION_KEY") or "")
    if not secret:
        raise MailDeliveryError("mail encryption key is not configured")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt_secret(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        raise MailDeliveryError("email settings cannot be decrypted") from None


def settings_row() -> MailSettings | None:
    return MailSettings.query.order_by(MailSettings.created_at.asc()).first()


def _empty_config() -> dict:
    return {"provider": "resend", "sender": "", "fallback": False,
            "resend_secret": "", "smtp": {}, "source": "none"}


def env_config() -> dict | None:
    key = str(current_app.config.get("RESEND_API_KEY") or "").strip()
    if not key:
        return None
    return {"provider": "resend", "sender": str(current_app.config.get("RESEND_FROM") or DEFAULT_SENDER),
            "fallback": False, "resend_secret": key, "smtp": {}, "source": "environment"}


def row_config(row: MailSettings) -> dict:
    return {
        "provider": row.provider,
        "sender": row.sender or "",
        "fallback": bool(row.fallback),
        "resend_secret": decrypt_secret(row.resend_secret) if row.resend_secret else "",
        "smtp": {**row.smtp_dict(), "secret": decrypt_secret(row.smtp_secret) if row.smtp_secret else ""},
        "source": "database",
    }


def active_config() -> dict:
    row = settings_row()
    if row:
        return row_config(row)
    return env_config() or _empty_config()


def provider_ready(config: dict, provider: str) -> bool:
    if not str(config.get("sender") or "").strip():
        return False
    if provider == "resend":
        return bool(config.get("resend_secret"))
    smtp = config.get("smtp") or {}
    if not (smtp.get("host") and smtp.get("port")):
        return False
    # Relays that ask for a username also need its password.
    return bool(smtp.get("secret")) or not smtp.get("username")


def describe_settings() -> dict:
    """Admin view: non-secret fields plus whether each provider is usable."""
    row = settings_row()
    config = row_config(row) if row else (env_config() or _empty_config())
    smtp = config.get("smtp") or {}
    return {
        "source": config.get("source", "none"),
        "provider": config.get("provider", "resend"),
        "sender": config.get("sender") or "",
        "fallback": bool(config.get("fallback")),
        "resend": {"secret_saved": bool(config.get("resend_secret")),
                   "configured": provider_ready(config, "resend")},
        "smtp": {"secret_saved": bool(smtp.get("secret")), "host": smtp.get("host") or "",
                 "port": smtp.get("port"), "security": smtp.get("security") or "",
                 "username": smtp.get("username") or "", "configured": provider_ready(config, "smtp")},
        "updated_at": iso(row.updated_at) if row else None,
        "last_test": row.last_test if row else None,
    }


def validate_sender(value) -> str:
    sender = str(value or "").strip()
    if not sender or len(sender) > 200:
        raise ValueError("invalid sender address")
    _, address = parseaddr(sender)
    if not ADDRESS_PATTERN.match(address):
        raise ValueError("invalid sender address")
    return sender


def validate_recipient(value) -> str:
    address = str(value or "").strip()
    if len(address) > 255 or not ADDRESS_PATTERN.match(address):
        raise ValueError("invalid email address")
    return address


def validate_smtp_host(value) -> str:
    host = str(value or "").strip()
    if not HOST_PATTERN.match(host) or "." not in host:
        raise ValueError("invalid smtp host")
    return host


def validate_smtp_port(value) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ValueError("invalid smtp port") from None
    if port < 1 or port > 65535:
        raise ValueError("invalid smtp port")
    return port


def _secret_value(value, saved: str) -> str:
    """Blank keeps the saved secret, null clears it, anything else replaces it."""
    if value is None and saved:
        return ""
    text = str(value or "").strip()
    if not text:
        return saved or ""
    if len(text) > 400 or any(character.isspace() for character in text):
        raise ValueError("email settings are invalid")
    return text


def normalize_config(data: dict, row: MailSettings | None) -> dict:
    """Merge an admin payload onto the saved config, validating every field."""
    base = row_config(row) if row else (env_config() or _empty_config())
    provider = str(data.get("provider") or base["provider"]).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("email provider is not supported")
    config = {
        "provider": provider,
        "sender": validate_sender(data.get("sender", base["sender"])),
        "fallback": bool(data.get("fallback", base["fallback"])),
        "resend_secret": _secret_value(data["resend_secret"], base.get("resend_secret", ""))
        if "resend_secret" in data else base.get("resend_secret", ""),
        "smtp": dict(base.get("smtp") or {}),
        "source": "database",
    }
    smtp = config["smtp"]
    if provider == "smtp" or any(field in data for field in SMTP_FIELDS):
        smtp["host"] = validate_smtp_host(data.get("smtp_host", smtp.get("host", "")))
        smtp["port"] = validate_smtp_port(data.get("smtp_port", smtp.get("port")))
        security = str(data.get("smtp_security", smtp.get("security", "")) or "").strip().lower()
        if security not in SMTP_SECURITIES:
            raise ValueError("invalid smtp security")
        smtp["security"] = security
        username = str(data.get("smtp_username", smtp.get("username", "")) or "").strip()
        if len(username) > 200:
            raise ValueError("invalid smtp username")
        smtp["username"] = username
        if "smtp_secret" in data:
            smtp["secret"] = _secret_value(data["smtp_secret"], smtp.get("secret", ""))
    return config


def save_config(config: dict, actor_id: str | None) -> MailSettings:
    row = settings_row() or MailSettings()
    if row not in db.session:
        db.session.add(row)
    smtp = config.get("smtp") or {}
    row.provider = config["provider"]
    row.sender = config["sender"]
    row.fallback = bool(config.get("fallback"))
    row.resend_secret = encrypt_secret(config["resend_secret"]) if config.get("resend_secret") else None
    row.smtp_host = smtp.get("host") or None
    row.smtp_port = smtp.get("port") or None
    row.smtp_security = smtp.get("security") or None
    row.smtp_username = smtp.get("username") or None
    row.smtp_secret = encrypt_secret(smtp["secret"]) if smtp.get("secret") else None
    row.updated_by = actor_id
    db.session.flush()
    return row


def send_mail(to: str, subject: str, text: str, html: str = "",
              *, config: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Deliver one message, optionally failing over to the other provider."""
    config = config or active_config()
    if not provider_ready(config, config["provider"]):
        raise MailDeliveryError("email delivery is not configured", provider=config["provider"])
    order = [config["provider"]]
    if config.get("fallback"):
        alternate = "smtp" if config["provider"] == "resend" else "resend"
        if provider_ready(config, alternate):
            order.append(alternate)
    failure = MailDeliveryError("email delivery is not configured", provider=config["provider"])
    for provider in order:
        try:
            _deliver(provider, config, to, subject, text, html, timeout)
        except MailDeliveryError as error:
            failure = error
            continue
        return {"provider": provider, "fallback_used": provider != config["provider"]}
    raise failure


def _deliver(provider: str, config: dict, to: str, subject: str, text: str, html: str, timeout: int) -> None:
    if provider == "resend":
        _send_resend(config, to, subject, text, html, timeout)
    else:
        _send_smtp(config, to, subject, text, html, timeout)


def _send_resend(config: dict, to: str, subject: str, text: str, html: str, timeout: int) -> None:
    payload = {"from": config["sender"], "to": [to], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['resend_secret']}",
            "Content-Type": "application/json",
            "User-Agent": "uestc-ai-platform/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise MailDeliveryError("email provider rejected the request", provider="resend",
                                        detail=f"HTTP {response.status}")
    except HTTPError as error:
        raise MailDeliveryError("email provider rejected the request", provider="resend",
                                detail=f"HTTP {error.code} {error.reason}") from error
    except MailDeliveryError:
        raise
    except (URLError, TimeoutError) as error:
        raise MailDeliveryError("email provider is unavailable", provider="resend", detail=error) from error


def _send_smtp(config: dict, to: str, subject: str, text: str, html: str, timeout: int) -> None:
    smtp = config["smtp"]
    message = EmailMessage()
    message["From"] = config["sender"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    host, port = smtp["host"], int(smtp["port"])
    context = ssl.create_default_context()
    try:
        if smtp.get("security") == "starttls":
            server = smtplib.SMTP(host, port, timeout=timeout)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
        try:
            if smtp.get("username"):
                server.login(smtp["username"], smtp.get("secret") or "")
            refused = server.send_message(message)
            if refused:
                raise MailDeliveryError("email provider rejected the request", provider="smtp",
                                        detail="recipient refused: " + ", ".join(sorted(refused)))
        finally:
            try:
                server.quit()
            except (smtplib.SMTPException, OSError):
                pass
    except smtplib.SMTPAuthenticationError as error:
        raise MailDeliveryError("email provider rejected the request", provider="smtp",
                                detail=f"authentication failed ({error.smtp_code})") from error
    except smtplib.SMTPException as error:
        raise MailDeliveryError("email provider rejected the request", provider="smtp", detail=error) from error
    except MailDeliveryError:
        raise
    except (ssl.SSLError, OSError) as error:
        raise MailDeliveryError("email provider is unavailable", provider="smtp", detail=error) from error


def test_delivery(recipient: str, *, config: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Send one message and report the outcome without raising."""
    config = config or active_config()
    started = time.monotonic()
    outcome = {"recipient": recipient, "sender": config.get("sender") or "",
               "provider": config.get("provider", ""), "fallback_used": False,
               "ok": False, "reason": "", "detail": ""}
    try:
        result = send_mail(recipient, "UESTC AI 邮件服务测试",
                           "这是一封来自 UESTC AI 平台管理后台的测试邮件，用于确认邮件通道可用，可忽略。",
                           config=config, timeout=timeout)
        outcome.update({"ok": True, "provider": result["provider"], "fallback_used": result["fallback_used"]})
    except MailDeliveryError as error:
        outcome["provider"] = error.provider or config.get("provider", "")
        outcome["reason"] = error.message
        outcome["detail"] = error.detail
    outcome["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    outcome["at"] = iso(utcnow())
    return outcome
