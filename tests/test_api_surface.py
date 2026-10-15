"""Positive contracts for API routes missing from the original regression suite."""
import io
import unittest
import test_backend_api as fixtures


class ApiSurfaceTests(unittest.TestCase):
    setUp = fixtures.PlatformApiTestCase.setUp
    tearDown = fixtures.PlatformApiTestCase.tearDown
    login = fixtures.PlatformApiTestCase.login
    register = fixtures.PlatformApiTestCase.register

    def test_admin_lists_roles_invites_and_audit(self):
        self.login(self.admin, "admin@uestcai.top")
        self.register(self.member, "surface@std.uestc.edu.cn", "Surface")
        paths = ["/admin/users", "/admin/audit", "/ai/manage/teams", "/manage/checkpoints", "/manage/problem-runtimes", "/manage/registrations", "/manage/score-batches", "/manage/submissions"]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.app.test_client().get("/api"+path).status_code, 401)
                self.assertEqual(self.member.get("/api"+path).status_code, 403)
                response = self.admin.get("/api"+path)
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertIsNotNone(response.get_json())
        users = self.admin.get("/api/admin/users?q=surface").get_json()
        self.assertEqual(len(users), 1)
        user_id = users[0]["id"]
        self.assertEqual(self.admin.patch(f"/api/admin/users/{user_id}", json={"role":"invalid"}).status_code, 400)
        changed = self.admin.patch(f"/api/admin/users/{user_id}", json={"role":"reviewer"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["role"], "reviewer")
        invite = self.admin.post("/api/admin/registration-invites", json={"note":"audit"})
        self.assertEqual(invite.status_code, 201)
        revoked = self.admin.delete("/api/admin/registration-invites/"+invite.get_json()["id"])
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(revoked.get_json()["status"], "revoked")
        self.assertTrue(any(row["action"] == "user.role_changed" for row in self.admin.get("/api/admin/audit").get_json()))

    def test_team_join_track_update_health_and_csv_batch(self):
        self.assertEqual(self.member.get("/api/health").status_code, 200)
        self.login(self.admin, "admin@uestcai.top")
        self.register(self.member, "captain@std.uestc.edu.cn", "Captain")
        comp = self.member.get("/api/competitions/paper-city-2027").get_json()
        track = next(t for t in comp["tracks"] if t["slug"] == "story-maps")
        problem = track["problems"][0]
        updated = self.admin.patch("/api/manage/tracks/"+track["id"], json={"name":"Updated track"})
        self.assertEqual(updated.status_code, 200)
        detail = self.member.get(f"/api/competitions/{comp['slug']}/tracks/{track['slug']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["name"], "Updated track")
        team_response = self.member.post("/api/teams", json={"competition_id":comp["id"], "name":"Surface team"})
        self.assertEqual(team_response.status_code, 201)
        team = team_response.get_json()
        second = self.app.test_client()
        self.register(second, "joining@std.uestc.edu.cn", "Joining")
        self.assertEqual(second.post("/api/teams/join", json={"invite_code":"MISSING"}).status_code, 404)
        joined = second.post("/api/teams/join", json={"invite_code":team["invite_code"]})
        self.assertEqual(joined.status_code, 200, joined.get_json())
        mine = second.get("/api/me/teams")
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.get_json()[0]["id"], team["id"])
        registration = self.member.post("/api/registrations", json={"competition_id":comp["id"],"track_id":track["id"],"team_id":team["id"]})
        self.assertEqual(registration.status_code, 201)
        submitted = self.member.post("/api/submissions", json={"problem_id":problem["id"],"team_id":team["id"],"title":"CSV test","readme_md":"# Test","fields":{"repository":"https://example.test/repository"},"status":"submitted"})
        self.assertEqual(submitted.status_code, 201, submitted.get_json())
        version = submitted.get_json()["version"]["id"]
        asset = self.member.post(f"/api/submission-versions/{version}/assets", data={"visibility":"public","file":(io.BytesIO(b"test bytes"),"result.csv")}, content_type="multipart/form-data")
        self.assertEqual(asset.status_code, 201)
        downloaded = self.member.get("/api/assets/"+asset.get_json()["id"])
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.data, b"test bytes")
        enabled = self.admin.patch("/api/manage/problems/"+problem["id"], json={"scoring_config":{"external_weight_percent":100}})
        self.assertEqual(enabled.status_code, 200, enabled.get_json())
        csv = f"submission_version_id,total_score\n{version},72.5\n".encode()
        imported = self.admin.post("/api/scores/import-csv", data={"competition_id":comp["id"],"problem_id":problem["id"],"file":(io.BytesIO(csv),"scores.csv")}, content_type="multipart/form-data")
        self.assertEqual(imported.status_code, 201, imported.get_json())
        self.assertEqual(imported.get_json()["accepted"], 1)
        batch = imported.get_json()["batch_id"]
        self.assertEqual(self.admin.patch(f"/api/manage/score-batches/{batch}", json={"status":"invalid"}).status_code, 400)
        changed = self.admin.patch(f"/api/manage/score-batches/{batch}", json={"status":"confirmed"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.get_json()["status"], "confirmed")
        rows = self.admin.get("/api/manage/score-batches").get_json()
        self.assertEqual(next(row for row in rows if row["id"] == batch)["score_count"], 1)
