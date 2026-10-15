"""Admin configuration for outbound verification mail."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..mailer import (MailDeliveryError, active_config, describe_settings, normalize_config,
                      save_config, settings_row, test_delivery, validate_recipient)
from ..security import current_user, require_user
from ..utils import audit

mail_bp = Blueprint("mail", __name__)


@mail_bp.get("/manage/mail")
@require_user("admin")
def read_mail_settings():
    """Current provider, non-secret fields and whether each channel is usable."""
    return jsonify(describe_settings())


@mail_bp.put("/manage/mail")
@require_user("admin")
def update_mail_settings():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid request body"}), 400
    try:
        config = normalize_config(data, settings_row())
        row = save_config(config, getattr(current_user(), "id", None))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except MailDeliveryError as error:
        db.session.rollback()
        return jsonify({"error": error.message}), 503
    smtp = config.get("smtp") or {}
    audit("mail.settings_updated", "mail_settings", row.id, {
        "provider": config["provider"],
        "sender": config["sender"],
        "fallback": bool(config.get("fallback")),
        "resend_secret_saved": bool(config.get("resend_secret")),
        "smtp_host": smtp.get("host", ""),
        "smtp_security": smtp.get("security", ""),
        "smtp_secret_saved": bool(smtp.get("secret")),
    })
    db.session.commit()
    return jsonify(describe_settings())


@mail_bp.post("/manage/mail/test")
@require_user("admin")
def send_mail_test():
    """Send a real message; ``draft`` tests unsaved values before saving them."""
    data = request.get_json(silent=True) or {}
    draft = data.get("draft")
    try:
        recipient = validate_recipient(data.get("recipient"))
        config = normalize_config(draft, settings_row()) if isinstance(draft, dict) else active_config()
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except MailDeliveryError as error:
        return jsonify({"error": error.message}), 503
    result = test_delivery(recipient, config=config)
    row = settings_row()
    if row is not None:
        row.last_test = result
    audit("mail.test_sent", "mail_settings", row.id if row else "unconfigured", {
        "recipient": recipient,
        "provider": result.get("provider", ""),
        "ok": bool(result.get("ok")),
        "reason": result.get("reason", ""),
    })
    db.session.commit()
    return jsonify(result)
