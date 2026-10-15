"""Admin-configurable mail delivery: Resend or SMTP, encrypted secrets."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from platform_api import mailer
from platform_api.mail_models import MailSettings
from platform_api.mailer import MailDeliveryError, decrypt_secret
from platform_api.models import AuditLog, User
from tests import test_backend_api as base_tests


class MailSettingsTestCase(unittest.TestCase):
    login = base_tests.PlatformApiTestCase.login

    def setUp(self):
        base_tests.PlatformApiTestCase.setUp(self)
        self.app.config["MAIL_ENCRYPTION_KEY"] = "mail-test-encryption-key"
        self.login(self.admin, "admin@uestcai.top")

    def tearDown(self):
        base_tests.PlatformApiTestCase.tearDown(self)

    def smtp_payload(self, **overrides):
        payload = {"provider": "smtp", "sender": "UESTC AI <noreply@uestcai.top>",
                   "smtp_host": "smtpdm.aliyun.com", "smtp_port": 465, "smtp_security": "ssl",
                   "smtp_username": "noreply@uestcai.top", "smtp_secret": "smtp-password-123"}
        payload.update(overrides)
        return payload

    def test_mail_settings_are_admin_only(self):
        self.assertEqual(self.member.get("/api/manage/mail").status_code, 401)
        self.assertEqual(self.member.put("/api/manage/mail", json=self.smtp_payload()).status_code, 401)
        self.assertEqual(self.member.post("/api/manage/mail/test", json={"recipient": "a@b.com"}).status_code, 401)
        self.login(self.reviewer, "reviewer@uestc.ai")
        self.assertEqual(self.reviewer.get("/api/manage/mail").status_code, 403)
        self.assertEqual(self.reviewer.put("/api/manage/mail", json=self.smtp_payload()).status_code, 403)
        self.assertEqual(self.reviewer.post("/api/manage/mail/test", json={"recipient": "a@b.com"}).status_code, 403)

    def test_environment_config_is_used_until_an_admin_saves(self):
        self.app.config["RESEND_API_KEY"] = ""
        body = self.admin.get("/api/manage/mail").get_json()
        self.assertEqual(body["source"], "none")
        self.assertFalse(body["resend"]["configured"])

        self.app.config["RESEND_API_KEY"] = "re_environment_key"
        self.app.config["RESEND_FROM"] = "UESTC AI <noreply@uestcai.top>"
        body = self.admin.get("/api/manage/mail").get_json()
        self.assertEqual(body["source"], "environment")
        self.assertEqual(body["provider"], "resend")
        self.assertTrue(body["resend"]["configured"])
        self.assertFalse(body["smtp"]["configured"])
        self.assertNotIn("re_environment_key", json.dumps(body))

    def test_admin_saves_smtp_config_and_the_secret_is_encrypted(self):
        response = self.admin.put("/api/manage/mail", json=self.smtp_payload())
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["source"], "database")
        self.assertEqual(body["provider"], "smtp")
        self.assertEqual(body["smtp"]["host"], "smtpdm.aliyun.com")
        self.assertEqual(body["smtp"]["port"], 465)
        self.assertTrue(body["smtp"]["secret_saved"])
        self.assertTrue(body["smtp"]["configured"])
        self.assertNotIn("smtp-password-123", json.dumps(body))

        with self.app.app_context():
            row = MailSettings.query.one()
            self.assertNotIn("smtp-password-123", row.smtp_secret)
            self.assertEqual(decrypt_secret(row.smtp_secret), "smtp-password-123")
            self.assertEqual(row.updated_by, User.query.filter_by(email="admin@uestcai.top").one().id)

    def test_blank_secret_keeps_the_saved_one_and_null_clears_it(self):
        self.admin.put("/api/manage/mail", json=self.smtp_payload())
        kept = self.admin.put("/api/manage/mail", json={"smtp_secret": ""}).get_json()
        self.assertTrue(kept["smtp"]["secret_saved"])
        self.assertTrue(kept["smtp"]["configured"])
        cleared = self.admin.put("/api/manage/mail", json={"smtp_secret": None}).get_json()
        self.assertFalse(cleared["smtp"]["secret_saved"])
        self.assertFalse(cleared["smtp"]["configured"])

    def test_invalid_values_are_rejected(self):
        cases = [
            ({"provider": "sendgrid"}, "email provider is not supported"),
            ({**self.smtp_payload(), "sender": "not-an-address"}, "invalid sender address"),
            (self.smtp_payload(smtp_host="bad host"), "invalid smtp host"),
            (self.smtp_payload(smtp_port=70000), "invalid smtp port"),
            (self.smtp_payload(smtp_security="plain"), "invalid smtp security"),
            (self.smtp_payload(smtp_secret="has space"), "email settings are invalid"),
        ]
        for payload, message in cases:
            response = self.admin.put("/api/manage/mail", json=payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(response.get_json()["error"], message, payload)

    def test_saving_a_secret_requires_the_encryption_key(self):
        self.app.config["MAIL_ENCRYPTION_KEY"] = ""
        self.app.config["AI_GATEWAY_ENCRYPTION_KEY"] = ""
        response = self.admin.put("/api/manage/mail", json=self.smtp_payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "mail encryption key is not configured")
        with self.app.app_context():
            self.assertIsNone(MailSettings.query.first())

    def test_test_endpoint_reports_success_and_failure(self):
        self.admin.put("/api/manage/mail", json=self.smtp_payload())
        failure = MailDeliveryError("email provider rejected the request", provider="smtp",
                                    detail="authentication failed (535)")
        with patch.object(mailer, "_send_smtp", side_effect=failure):
            response = self.admin.post("/api/manage/mail/test", json={"recipient": "captain@std.uestc.edu.cn"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["reason"], "email provider rejected the request")
        self.assertIn("535", body["detail"])
        self.assertEqual(body["provider"], "smtp")

        with patch.object(mailer, "_send_smtp") as sender:
            body = self.admin.post("/api/manage/mail/test", json={"recipient": "captain@std.uestc.edu.cn"}).get_json()
        self.assertEqual(sender.call_count, 1)
        self.assertTrue(body["ok"])
        self.assertFalse(body["fallback_used"])
        self.assertGreaterEqual(body["elapsed_ms"], 0)
        with self.app.app_context():
            self.assertTrue(MailSettings.query.one().last_test["ok"])

        self.assertEqual(self.admin.post("/api/manage/mail/test", json={"recipient": "nope"}).status_code, 400)

    def test_draft_config_is_tested_before_saving(self):
        with patch.object(mailer, "_send_smtp") as sender:
            response = self.admin.post("/api/manage/mail/test",
                                       json={"recipient": "captain@std.uestc.edu.cn", "draft": self.smtp_payload()})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue(response.get_json()["ok"])
        self.assertEqual(sender.call_count, 1)
        with self.app.app_context():
            self.assertIsNone(MailSettings.query.first())

    def test_fallback_delivers_through_the_other_provider(self):
        self.admin.put("/api/manage/mail",
                       json=self.smtp_payload(provider="resend", fallback=True, resend_secret="re_live_key"))
        unavailable = MailDeliveryError("email provider is unavailable", provider="resend")
        with patch.object(mailer, "_send_resend", side_effect=unavailable), \
                patch.object(mailer, "_send_smtp") as smtp_sender:
            body = self.admin.post("/api/manage/mail/test",
                                   json={"recipient": "captain@std.uestc.edu.cn"}).get_json()
        self.assertEqual(smtp_sender.call_count, 1)
        self.assertTrue(body["ok"])
        self.assertEqual(body["provider"], "smtp")
        self.assertTrue(body["fallback_used"])

    def test_verification_codes_use_the_saved_provider(self):
        self.app.config["RESEND_API_KEY"] = "re_environment_key"
        self.admin.put("/api/manage/mail", json=self.smtp_payload())
        used = []
        self.app.config["TESTING"] = False
        try:
            with patch.object(mailer, "_deliver", side_effect=lambda provider, *args, **kwargs: used.append(provider)):
                with self.app.app_context():
                    mailer.send_verification_email("captain@std.uestc.edu.cn", "123456")
        finally:
            self.app.config["TESTING"] = True
        self.assertEqual(used, ["smtp"])

    def test_mail_changes_are_audited_without_secrets(self):
        self.admin.put("/api/manage/mail", json=self.smtp_payload())
        with self.app.app_context():
            entry = AuditLog.query.filter_by(action="mail.settings_updated").one()
            self.assertEqual(entry.details["provider"], "smtp")
            self.assertEqual(entry.details["smtp_host"], "smtpdm.aliyun.com")
            self.assertTrue(entry.details["smtp_secret_saved"])
            self.assertNotIn("smtp-password-123", json.dumps(entry.details))
