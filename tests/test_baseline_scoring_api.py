"""Real API/DB wiring with deterministic worker metrics, not GPU acceptance."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_backend_api as fixtures
import test_independent_evaluation_trials as trials


class BaselineScoreAPITests(unittest.TestCase):
    setUp = fixtures.PlatformApiTestCase.setUp
    tearDown = fixtures.PlatformApiTestCase.tearDown
    login = fixtures.PlatformApiTestCase.login
    register = fixtures.PlatformApiTestCase.register
    fixture = trials.IndependentTrialTests.fixture
    stage = trials.IndependentTrialTests.stage
    start = trials.IndependentTrialTests.start
    claim = trials.IndependentTrialTests.claim
    formal = trials.IndependentTrialTests.formal

    def test_frozen_reference_selected_result_and_trusted_review(self):
        self.fixture(adapter="classification-v1", limit=3)
        self.config["metrics"] = ["accuracy", "macro_f1", "latency_ms"]
        scoring = {"preset": "wujie-depth-baseline-v2", "criterion": "项目成果",
                   "reference": {"baseline_accuracy": 60, "gain_span_pp": 10, "latency_ms": 100}}
        body = {"evaluation_config": self.config, "scoring_config": {"review_score_mode": "weighted", "performance_scoring": scoring},
                "judging_schema": {"rubric": {"项目成果": .8, "技术说明": .2}}}
        response = self.admin.patch(f"/api/manage/problems/{self.problem['id']}", json=body)
        self.assertEqual(response.status_code, 200, response.get_json())
        asset = self.stage()
        started = self.start(asset)
        self.assertEqual(started.status_code, 201, started.get_json())
        job = self.claim()
        changed = deepcopy(body)
        changed["scoring_config"]["performance_scoring"]["reference"]["baseline_accuracy"] = 65
        self.assertEqual(self.admin.patch(f"/api/manage/problems/{self.problem['id']}", json=changed).status_code, 409)
        response = self.worker.post(f"/api/evaluation-worker/runs/{job['id']}/complete",
            headers={"X-Evaluation-Lease": job["lease_token"]},
            json={"status": "completed", "episodes": [{"accuracy": 65, "macro_f1": 60, "latency_ms": 200}]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["performance"]["score"], 81)
        self.assertEqual(response.get_json()["performance"]["reference"], scoring["reference"])
        submitted = self.formal(asset, job["id"])
        self.assertEqual(submitted.status_code, 201, submitted.get_json())
        self.assertEqual(self.member.get(self.budget_url).get_json()["used_runs"], 1)
        self.login(self.reviewer, "reviewer@uestc.ai")
        review = self.reviewer.post("/api/reviews", json={"submission_version_id": submitted.get_json()["version"]["id"],
            "scores": {"项目成果": 1, "技术说明": 80}, "total_score": 1})
        self.assertEqual(review.status_code, 201, review.get_json())
        self.assertEqual(review.get_json()["scores"]["项目成果"], 81)
        self.assertAlmostEqual(review.get_json()["total_score"], 80.8)


if __name__ == "__main__":
    unittest.main()
