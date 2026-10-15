"""Isolated audit probe: report Docker pre-execution infrastructure refund behavior."""
import json
from test_independent_evaluation_trials import IndependentTrialTests


def main():
    case=IndependentTrialTests()
    case.setUp()
    try:
        case.fixture()
        started=case.start(case.stage()).get_json()
        job=case.claim()
        response=case.worker.post(f"/api/evaluation-worker/runs/{job['id']}/complete",headers={"X-Evaluation-Lease":job["lease_token"]},json={"status":"failed","failure_kind":"infrastructure_before_execution","error":"trusted controller image unavailable before agent execution"})
        result=response.get_json()
        budget=case.member.get(case.budget_url).get_json()
        report={"scope":"isolated SQLite test fixture; no actual provider/Docker invocation","check":"Docker infrastructure failure before participant execution refunds trial opportunity","status":response.status_code,"expected_used_runs":0,"actual_used_runs":budget["used_runs"],"quota_refunded":result.get("quota_refunded"),"api_calls_used":result.get("api_calls_used"),"passed":budget["used_runs"]==0 and result.get("quota_refunded") is True}
        print(json.dumps(report))
    finally:
        case.tearDown()


if __name__=="__main__":main()
