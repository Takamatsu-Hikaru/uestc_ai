import io
import json
import sys
import unittest
import zipfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_compute_resources as fixtures
from platform_api.compute import provision_compute, remove_unused_compute
from platform_api.compute_models import ComputeAccount, ComputeGrant, ComputePolicy, ComputeProvider, ComputeSession, ComputeWorkerHeartbeat
from platform_api.extensions import db
from platform_api.models import AuditLog, Competition, Session, Team, User, utcnow
from platform_api.security import hash_token


class ManualComputeAccountsTests(unittest.TestCase):
    setUp = fixtures.ComputeResourcesTest.setUp
    close = fixtures.ComputeResourcesTest.close
    save_quota = fixtures.ComputeResourcesTest.save_quota
    start = fixtures.ComputeResourcesTest.start

    @classmethod
    def setUpClass(cls):
        fixtures.ComputeResourcesTest.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixtures.ComputeResourcesTest.tearDownClass.__func__(cls)

    def manual(self, **changes):
        config = {"mode": "manual_account", "enabled": True,
                  "login_url": "https://www.autodl.com/login", "instructions": "Use the provided training image", **changes}
        return self.save_quota(config)

    def issue(self, team="team", **changes):
        return self.admin.put(f"/api/compute/manage/problems/problem/accounts/{team}", json={
            "username": "team-private-login", "password": "team-private-password",
            "notes": "private-account-instructions", "enabled": True, **changes})

    def reveal(self, account_id, client=None):
        return (client or self.member).post(f"/api/compute/accounts/{account_id}/credentials")

    def test_manual_mode_needs_no_provider_or_worker_and_new_teams_need_no_grants(self):
        with self.app.app_context():
            ComputeGrant.query.delete(); ComputePolicy.query.delete(); ComputeProvider.query.delete()
            ComputeWorkerHeartbeat.query.delete(); db.session.commit()
        with patch("platform_api.routes.compute.AutoDL", side_effect=AssertionError("no provider calls")):
            self.manual()
            overview = self.member.get("/api/compute/overview").json
            self.assertEqual(overview["grants"], [])
            self.assertFalse(overview["worker_online"])
            self.assertEqual(overview["manual_accounts"][0]["status"], "pending")
            saved_key = self.app.config["AI_GATEWAY_ENCRYPTION_KEY"]
            self.app.config["AI_GATEWAY_ENCRYPTION_KEY"] = ""
            checks = self.admin.get("/api/manage/problems/problem/setup").json["checks"]
            self.assertEqual(next(c for c in checks if c["key"] == "compute")["state"], "blocked")
            self.app.config["AI_GATEWAY_ENCRYPTION_KEY"] = saved_key
            self.assertEqual(self.issue().status_code, 200)
            with self.app.app_context():
                team = Team(id="future", competition_id="comp", name="Future", captain_id="member", invite_code="future")
                db.session.add(team); db.session.flush(); provision_compute(team); db.session.commit()
                self.assertEqual(ComputeGrant.query.count(), 0)
            self.assertEqual(len(self.admin.get("/api/compute/manage/problems/problem/accounts").json), 3)
        self.assertEqual(fixtures.AutoDLService.calls, [])

    def test_credentials_are_encrypted_private_and_absent_from_lists_audits_and_exports(self):
        self.manual()
        issued = self.issue(); self.assertEqual(issued.status_code, 200)
        account_id = issued.json["id"]
        own = self.reveal(account_id)
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json["password"], "team-private-password")
        self.assertIn("no-store", own.headers["Cache-Control"])
        for client in (self.other, self.reviewer, self.app.test_client()):
            self.assertIn(self.reveal(account_id, client).status_code, (401, 403))
        self.assertEqual(self.reveal(account_id, self.admin).status_code, 200)
        for client in (self.admin, self.member, self.other, self.reviewer):
            overview = client.get("/api/compute/overview")
            self.assertNotIn("team-private", overview.get_data(as_text=True))
            self.assertNotIn("private-account-instructions", overview.get_data(as_text=True))
        self.assertEqual(self.reviewer.get("/api/compute/overview").json["manual_accounts"], [])
        listing = self.admin.get("/api/compute/manage/problems/problem/accounts").get_data(as_text=True)
        self.assertNotIn("team-private", listing)
        with self.app.app_context():
            saved = db.session.get(ComputeAccount, account_id)
            self.assertNotIn("team-private", saved.secret)
            self.assertNotIn("private-account-instructions", saved.secret)
            self.assertNotIn("team-private", str([a.details for a in AuditLog.query.all()]))
        export = self.admin.get("/api/manage/problems/problem/package")
        self.assertEqual(export.status_code, 200, export.get_data(as_text=True)[:200] if export.status_code != 200 else "")
        with zipfile.ZipFile(io.BytesIO(export.data)) as archive:
            self.assertNotIn("team-private", str([archive.read(n) for n in archive.namelist()]))
            manifest = json.loads(archive.read("problem.json"))
            self.assertEqual(manifest["setup"]["compute"]["mode"], "manual_account")
            self.assertNotIn("provider", json.loads(archive.read("connections.json")))

    def test_only_admin_can_issue_and_foreign_competition_is_rejected(self):
        self.manual()
        for client in (self.member, self.other, self.reviewer):
            response = client.put("/api/compute/manage/problems/problem/accounts/team", json={})
            self.assertEqual(response.status_code, 403)
        with self.app.app_context():
            competition = Competition(id="elsewhere", name="Other", slug="other", summary="Other", status="published")
            db.session.add(competition)
            db.session.add(Team(id="foreign", competition=competition, name="Foreign", captain_id="member", invite_code="foreign"))
            db.session.commit()
        self.assertEqual(self.issue("foreign").status_code, 400)
        self.assertEqual(self.issue("missing").status_code, 400)

    def test_organizer_can_see_status_but_not_credentials_or_issue(self):
        self.manual(); account_id = self.issue().json["id"]
        with self.app.app_context():
            db.session.add(User(id="org", email="org@example.com", name="Org", role="organizer", password_hash="unused"))
            db.session.add(Session(token_hash=hash_token("org"), user_id="org", expires_at=utcnow()+timedelta(days=1)))
            db.session.commit()
        organizer = self.app.test_client(); organizer.set_cookie("session_token", "org")
        self.assertEqual(organizer.get("/api/compute/manage/problems/problem/accounts").status_code, 200)
        self.assertEqual(self.reveal(account_id, organizer).status_code, 403)
        self.assertEqual(organizer.put("/api/compute/manage/problems/problem/accounts/team", json={}).status_code, 403)

    def test_switch_disables_managed_starts_preserves_usage_and_allows_switch_back(self):
        with self.app.app_context():
            grant = db.session.get(ComputeGrant, self.grant["id"]); grant.gpu_seconds_used = 120; db.session.commit()
        self.manual()
        self.start(status=409)
        self.assertEqual(self.member.get("/api/compute/overview").json["summary"]["gpu_seconds"], 120)
        with self.app.app_context():
            self.assertEqual(ComputeSession.query.count(), 0)
            self.assertFalse(db.session.get(ComputeGrant, self.grant["id"]).enabled)
        self.save_quota(self.config)
        self.assertEqual(self.member.get("/api/compute/overview").json["manual_accounts"], [])
        self.assertTrue(self.member.get("/api/compute/overview").json["grants"][0]["enabled"])
        self.assertEqual(fixtures.AutoDLService.calls, [])

    def test_live_sessions_block_switch_without_changing_the_policy_or_budget(self):
        self.start()
        before = self.member.get("/api/compute/overview").json
        self.save_quota({"mode": "manual_account", "enabled": True}, status=409)
        self.assertEqual(self.admin.get("/api/compute/manage/problems/problem/quota").json["config"], self.config)
        self.assertEqual(self.member.get("/api/compute/overview").json["summary"], before["summary"])

    def test_paused_policy_account_and_team_removal_revoke_viewing(self):
        self.manual(); account_id = self.issue().json["id"]
        url = "/api/compute/manage/problems/problem/accounts/team"
        self.assertEqual(self.admin.patch(url, json={"enabled": False}).status_code, 200)
        self.assertEqual(self.reveal(account_id).status_code, 403)
        self.admin.patch(url, json={"enabled": True})
        self.manual(enabled=False)
        self.assertEqual(self.reveal(account_id).status_code, 403)
        self.manual()
        self.assertEqual(self.reveal(account_id).status_code, 200)
        from platform_api.models import TeamMember
        with self.app.app_context():
            db.session.delete(db.session.get(TeamMember, ("team", "member"))); db.session.commit()
        self.assertEqual(self.reveal(account_id).status_code, 403)
        self.assertEqual(self.member.get("/api/compute/overview").json["manual_accounts"], [])

    def test_account_updates_keep_blank_password_and_policy_switch_hides_accounts(self):
        self.manual(); account_id = self.issue().json["id"]
        self.assertEqual(self.issue(username="updated-login", password="").status_code, 200)
        self.assertEqual(self.reveal(account_id).json["password"], "team-private-password")
        self.assertEqual(self.reveal(account_id).json["username"], "updated-login")
        with self.app.app_context(): self.assertEqual(ComputeAccount.query.count(), 1)
        self.save_quota(self.config)
        self.assertEqual(self.reveal(account_id).status_code, 409)
        self.manual()
        self.assertEqual(self.reveal(account_id).status_code, 200)

    def test_account_record_blocks_deletion(self):
        self.manual(); self.issue()
        with self.app.app_context():
            self.assertFalse(remove_unused_compute(team_id="team"))
            self.assertFalse(remove_unused_compute(problem_ids=["problem"]))

    def test_account_record_blocks_admin_cascades_without_losing_credentials(self):
        self.manual(); account_id = self.issue().json["id"]
        impact = self.admin.get("/api/manage/competitions/comp/deletion-impact")
        self.assertEqual(impact.status_code, 200)
        self.assertFalse(impact.json["can_delete"])
        self.assertEqual(impact.json["counts"]["manual_compute_accounts"], 1)
        with self.app.app_context():
            slug = db.session.get(Competition, "comp").slug
            email = db.session.get(User, "member").email
        deleted = self.admin.delete("/api/manage/competitions/comp", json={"confirm": slug})
        self.assertEqual(deleted.status_code, 409)
        user_impact = self.admin.get("/api/admin/users/member/deletion-impact")
        self.assertFalse(user_impact.json["can_delete"])
        deleted_user = self.admin.delete("/api/admin/users/member", json={"confirm": email})
        self.assertEqual(deleted_user.status_code, 409)
        self.assertEqual(self.reveal(account_id).status_code, 200)

    def test_invalid_account_and_policy_never_save(self):
        self.manual()
        for changes in ({"username": ""}, {"password": ""}, {"password": 123}, {"enabled": "yes"}, {"notes": "a"*4001}):
            self.assertEqual(self.issue(**changes).status_code, 400)
        for config in ({"mode": "unknown"}, {"mode": "manual_account", "login_url": "https://evil.example"},
                       {"mode": "manual_account", "login_url": "https://secret@www.autodl.com/login"},
                       {"mode": "manual_account", "provider_id": self.provider["id"]}):
            self.save_quota(config, status=400)
        with self.app.app_context(): self.assertEqual(ComputeAccount.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
