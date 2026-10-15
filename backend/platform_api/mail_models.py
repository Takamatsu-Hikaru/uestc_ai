"""Mail delivery settings.

A single row describes which provider the platform sends verification mail
through. Secrets are stored encrypted (see ``mailer.cipher``) and are never
included in any serializer; the API only reports whether one is saved.
"""
from __future__ import annotations

from .extensions import db
from .models import TimestampMixin, iso, new_id

PROVIDERS = ("resend", "smtp")
SMTP_SECURITIES = ("ssl", "starttls")


class MailSettings(TimestampMixin, db.Model):
    __tablename__ = "mail_settings"
    id = db.Column(db.String(36), primary_key=True, default=new_id)
    provider = db.Column(db.String(16), nullable=False, default="resend")
    sender = db.Column(db.String(200), nullable=False, default="")
    fallback = db.Column(db.Boolean, nullable=False, default=False)
    resend_secret = db.Column(db.Text)
    smtp_host = db.Column(db.String(200))
    smtp_port = db.Column(db.Integer)
    smtp_security = db.Column(db.String(16))
    smtp_username = db.Column(db.String(200))
    smtp_secret = db.Column(db.Text)
    updated_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    last_test = db.Column(db.JSON)

    def smtp_dict(self) -> dict:
        return {"host": self.smtp_host or "", "port": self.smtp_port,
                "security": self.smtp_security or "", "username": self.smtp_username or ""}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "sender": self.sender,
            "fallback": bool(self.fallback),
            "has_resend_secret": bool(self.resend_secret),
            "smtp_host": self.smtp_host or "",
            "smtp_port": self.smtp_port,
            "smtp_security": self.smtp_security or "",
            "smtp_username": self.smtp_username or "",
            "has_smtp_secret": bool(self.smtp_secret),
            "updated_at": iso(self.updated_at),
            "last_test": self.last_test,
        }
