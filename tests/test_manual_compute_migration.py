import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text
from platform_api import create_app
from platform_api.compute_models import ComputeAccount, ComputePolicy
from platform_api.extensions import db
from platform_api.models import Competition, Problem, Team, Track, User


class ManualComputeMigrationTests(unittest.TestCase):
    def test_upgrade_roundtrip_and_issued_account_downgrade_protection(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_app({"TESTING": True, "SEED_DATABASE": False, "AUTO_CREATE_SCHEMA": False,
                              "UPLOAD_FOLDER": root, "SQLALCHEMY_DATABASE_URI": "sqlite:///"+(Path(root)/"migration.sqlite").as_posix()})
            with app.app_context():
                try:
                    upgrade()
                    self.assertIn("compute_accounts", inspect(db.engine).get_table_names())
                    self.assertEqual(db.session.execute(text("PRAGMA foreign_key_check")).all(), [])
                    db.session.remove(); downgrade(revision="b0479d2e8a61"); upgrade()
                    user = User(id="member", email="test@example.com", name="Test", password_hash="unused")
                    competition = Competition(id="comp", name="Test", slug="test", summary="Test")
                    track = Track(id="track", competition=competition, name="Track", slug="track")
                    problem = Problem(id="problem", track=track, code="P", slug="p", title="Test")
                    team = Team(id="team", competition=competition, name="Team", captain_id="member", invite_code="TEAM")
                    db.session.add_all([user, problem, team]); db.session.commit()
                    policy = ComputePolicy(problem_id="problem", config={"mode": "manual_account", "enabled": True})
                    db.session.add(policy); db.session.commit(); db.session.remove()
                    with self.assertRaises(SystemExit): downgrade(revision="b0479d2e8a61")
                    upgrade(); db.session.delete(db.session.get(ComputePolicy, "problem"))
                    db.session.add(ComputeAccount(id="issued", team_id="team", problem_id="problem", secret="encrypted-test-data"))
                    db.session.commit(); db.session.remove()
                    with self.assertRaises(SystemExit): downgrade(revision="b0479d2e8a61")
                    self.assertEqual(db.session.get(ComputeAccount, "issued").secret, "encrypted-test-data")
                finally:
                    db.session.remove(); db.engine.dispose()
