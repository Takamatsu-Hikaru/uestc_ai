"""The mail_settings migration round-trips and matches the model."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

from platform_api import create_app
from platform_api.extensions import db


class MailSettingsMigrationTest(unittest.TestCase):
    def test_upgrade_creates_the_table_and_downgrade_removes_it(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_app({"AUTO_CREATE_SCHEMA": False, "SEED_DATABASE": False, "TESTING": True,
                              "UPLOAD_FOLDER": root, "MAIL_ENCRYPTION_KEY": "migration-test",
                              "SQLALCHEMY_DATABASE_URI":
                                  "sqlite:///" + (Path(root) / "migration.sqlite").as_posix()})
            with app.app_context():
                try:
                    upgrade(revision="c9f1a6e2087b")
                    self.assertNotIn("mail_settings", inspect(db.engine).get_table_names())
                    upgrade()
                    columns = {column["name"] for column in inspect(db.engine).get_columns("mail_settings")}
                    self.assertTrue({"id", "provider", "sender", "fallback", "resend_secret", "smtp_host",
                                     "smtp_port", "smtp_security", "smtp_username", "smtp_secret",
                                     "updated_by", "last_test", "created_at", "updated_at"} <= columns)
                    self.assertEqual(db.session.execute(text("PRAGMA foreign_key_check")).all(), [])
                    db.session.remove()
                    downgrade(revision="c9f1a6e2087b")
                    self.assertNotIn("mail_settings", inspect(db.engine).get_table_names())
                    upgrade()
                    self.assertIn("mail_settings", inspect(db.engine).get_table_names())
                finally:
                    db.session.remove()
                    db.engine.dispose()
