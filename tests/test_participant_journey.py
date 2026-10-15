"""Participant-to-reviewer contracts for both three-scene agent competitions.
The worker result is synthetic here; real simulation is tracked separately.
"""
import io
import json
import unittest
import zipfile
import test_backend_api as fixtures
import test_evaluation_limits as limits
from platform_api.extensions import db
from platform_api.models import Problem, ProblemRuntime
from evaluation_adapters.wujie_scenes import libero_scenes, minecraft_scenes


class ParticipantJourneyTests(unittest.TestCase):
    setUp = fixtures.PlatformApiTestCase.setUp
    tearDown = fixtures.PlatformApiTestCase.tearDown
    login = fixtures.PlatformApiTestCase.login
    register = fixtures.PlatformApiTestCase.register
    fixture = limits.EvaluationLimitTests.fixture

    def stage(self, marker="original"):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as archive:
            archive.writestr("agent.py", "class Agent: pass\n# "+marker)
            archive.writestr("config.json", "{}")
        response = self.member.post("/api/submission-assets/stage", data={"file":(io.BytesIO(raw.getvalue()),"agent.zip")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201)
        return response.get_json()["id"]

    def journey(self, adapter):
        self.fixture(limit=3)
        self.app.config["EVALUATION_ENABLED_ADAPTERS"] = adapter
        libero = adapter == "libero-agent-v1"
        self.config.update(adapter=adapter, task="manipulation" if libero else "open-world")
        self.config["resources"]["episodes"] = 3
        self.config["metrics"] = ["task_success"] if libero else ["task_success","exploration_progress"]
        scenes = libero_scenes((20,21,22),(100,101,102)) if libero else minecraft_scenes((100,101,102))
        with self.app.app_context():
            problem = db.session.get(Problem,self.problem["id"])
            problem.evaluation_config = self.config
            problem.scoring_config = {"review_score_mode":"weighted","performance_scoring":{"preset":"wujie-libero-v1" if libero else "wujie-world-v1","criterion":"表现"}}
            problem.judging_schema = {"rubric":{"表现":0.8,"技术路线":0.2}}
            db.session.add(ProblemRuntime(problem_id=problem.id,config={"image":"sha256:"+"a"*64,"agent_image":"sha256:"+"b"*64,"scenarios":scenes}))
            db.session.commit()
        asset = self.stage()
        path = f"/api/problems/{self.problem['id']}/evaluation-runs"
        body = {"team_id":self.team["id"],"staged_asset_ids":[asset]}
        started = self.member.post(path,json=body)
        self.assertEqual(started.status_code,201,started.get_json())
        run = started.get_json()
        # Double-click must not charge another trial.
        self.assertEqual(self.member.post(path,json=body).status_code,409)
        self.assertEqual(self.member.get(self.budget_url).get_json()["used_runs"],1)
        url = "/api/evaluation-runs/"+run["id"]
        self.assertEqual(self.app.test_client().get(url).status_code,401)
        other = self.app.test_client()
        self.register(other,"other@std.uestc.edu.cn","Other")
        self.assertEqual(other.get(url).status_code,403)
        public = self.member.get(url).get_data(as_text=True)
        self.assertNotIn("init_state_id",public)
        self.assertNotIn("world_seed",public)
        self.assertNotIn("sha256:",public)
        formal_body = {**self.fields,"staged_asset_ids":[asset],"evaluation_run_id":run["id"]}
        self.assertEqual(self.member.post("/api/submissions",json=formal_body).status_code,409)
        claimed = self.worker.post("/api/evaluation-worker/claim",headers={"Authorization":"Bearer test-worker"},json={"adapters":[adapter],"gpu":False,"managed_runtime":True,"memory_mb":8192})
        self.assertEqual(claimed.status_code,200,claimed.get_json())
        job = claimed.get_json()
        self.assertEqual(job["id"],run["id"])
        self.assertEqual(job["runtime"]["scenarios"],scenes)
        episodes = [{"task_success":success,**({"exploration_progress":progress} if not libero else {})} for success,progress in [(100,100),(0,50),(0,0)]]
        endpoint = f"/api/evaluation-worker/runs/{run['id']}/complete"
        headers = {"X-Evaluation-Lease":job["lease_token"]}
        self.assertEqual(self.worker.post(endpoint,headers=headers,json={"status":"completed","episodes":episodes[:2]}).status_code,400)
        completed = self.worker.post(endpoint,headers=headers,json={"status":"completed","episodes":episodes})
        self.assertEqual(completed.status_code,200,completed.get_json())
        self.assertEqual(len(completed.get_json()["episodes"]),3)
        expected = 100/3 if libero else 45
        self.assertAlmostEqual(completed.get_json()["performance"]["score"],expected,places=5)
        self.assertEqual(self.worker.post(endpoint,headers=headers,json={"status":"completed","episodes":episodes}).status_code,403)
        wrong = self.member.post("/api/submissions",json={**formal_body,"staged_asset_ids":[self.stage("changed")]})
        self.assertEqual(wrong.status_code,409)
        submitted = self.member.post("/api/submissions",json=formal_body)
        self.assertEqual(submitted.status_code,201,submitted.get_json())
        self.assertEqual(self.member.get(self.budget_url).get_json()["used_runs"],1)
        self.login(self.reviewer,"reviewer@uestc.ai")
        reviewed = self.reviewer.get(url)
        self.assertEqual(reviewed.status_code,200)
        self.assertEqual(reviewed.get_json()["performance"],completed.get_json()["performance"])
        work = self.member.get("/api/works/"+submitted.get_json()["id"])
        self.assertEqual(work.status_code,200)
        self.assertEqual(work.get_json()["evaluation"]["id"],run["id"])

    def test_libero_participant_to_reviewer_three_scene_result(self):
        self.journey("libero-agent-v1")

    def test_minedojo_participant_to_reviewer_three_scene_result(self):
        self.journey("minecraft-agent-v1")
