"""Offline harness regression: follow-ups, honest gaps, failures and ambiguous submission."""

import json

import httpx
import pytest

from .complex_evaluation import Case, Turn, check_result, evaluate_case, load_catalogue


def response_data():
    state = {
        "status": "completed",
        "progress": {
            "tasks": [],
            "source_versions": {"documents": "2fddb22824bee702", "northstar": "DEMO-2026-09-15-A"},
        },
    }
    result = {
        "answer": "The requested information is unavailable.",
        "review_status": "approved",
        "answer_package": {
            "resolved_request": "Unavailable data",
            "claims": [],
            "unresolved": [],
            "limitations": ["Source is not connected"],
            "source_conflicts": [],
            "clarification": None,
        },
        "evidence": {},
        "research": {},
    }
    return state, result


def make_case():
    return Case(
        id="EDGE28",
        title="Synthetic follow-up",
        category="limitations",
        expected_route="limitation",
        turns=[
            Turn(prompt="First question", require_claims=False, require_gap=True),
            Turn(prompt="Follow-up", require_claims=False, require_gap=True),
        ],
        review=["Inspect source support"],
        fail_if=["Invented result"],
    )


async def test_followups_reuse_thread_and_ambiguous_submission_keeps_identity(tmp_path):
    state, result = response_data()
    submissions = []

    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"research_enabled": True, "background_enabled": True})
        if request.method == "POST":
            submissions.append(json.loads(request.content))
            if len(submissions) == 1:
                raise httpx.ReadTimeout("Lost acknowledgement", request=request)
            return httpx.Response(202, json={"run_id": f"run-{len(submissions)}"})
        return httpx.Response(200, json=result if request.url.path.endswith("/result") else state)

    async with httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(handle)
    ) as c:
        report = await evaluate_case(c, load_catalogue(), make_case(), tmp_path, poll_seconds=0)
    assert submissions[0] == submissions[1]
    assert submissions[1]["thread_id"] == submissions[2]["thread_id"]
    assert submissions[1]["idempotency_key"] != submissions[2]["idempotency_key"]
    assert report["automated_status"] == "passed"
    assert report["semantic_review"]["status"] == "pending"
    assert len(report["turns"]) == 2
    assert json.loads(next(tmp_path.glob("*.json")).read_text()) == report


@pytest.mark.parametrize("quota", [False, True])
async def test_failed_run_is_reported_without_attempting_followup(tmp_path, quota):
    from comtech.agents.errors import ProviderQuotaExhausted

    state, _ = response_data()
    state["status"] = "failed"
    state["terminal_reason"] = "ProviderQuotaExhausted" if quota else "RuntimeError"
    submissions = []

    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"research_enabled": True, "background_enabled": True})
        if request.method == "POST":
            submissions.append(request)
            return httpx.Response(202, json={"run_id": "failed-run"})
        if "/threads/" in request.url.path:
            return httpx.Response(200, json=[{"run_id": "failed-run"}])
        if request.url.path.endswith("/result"):
            return httpx.Response(409, json={"status": "failed", "result_available": False})
        return httpx.Response(200, json=state)

    async with httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(handle)
    ) as c:
        with pytest.raises(ProviderQuotaExhausted if quota else AssertionError):
            await evaluate_case(c, load_catalogue(), make_case(), tmp_path)
    report = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert report["automated_status"] == "failed"
    assert report["turns"][0]["result_http_status"] == 409
    assert len(submissions) == 1


async def test_lost_submission_acknowledgements_discover_and_cancel_own_run(tmp_path):
    cancelled = []

    def handle(request):
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"research_enabled": True, "background_enabled": True})
        if request.url.path == "/api/runs":
            raise httpx.ReadTimeout("Lost acknowledgement", request=request)
        if "/threads/" in request.url.path:
            return httpx.Response(200, json=[{"run_id": "unacknowledged-run"}])
        if request.url.path.endswith("/cancel"):
            cancelled.append(request.url.path)
            return httpx.Response(200, json={"status": "cancel_requested"})
        return httpx.Response(200, json={"status": "running"})

    async with httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(handle)
    ) as c:
        with pytest.raises(httpx.ReadTimeout):
            await evaluate_case(c, load_catalogue(), make_case(), tmp_path)
    report = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert cancelled == ["/api/runs/unacknowledged-run/cancel"]
    assert report["cleanup"] == [{"run_id": "unacknowledged-run", "cancel_requested": True}]


@pytest.mark.parametrize("violation", ["review", "gap", "computation", "injection", "evidence"])
def test_structural_failures_are_not_quality_passes(violation):
    state, result = response_data()
    turn = Turn(prompt="Synthetic check", require_claims=False, require_gap=True)
    if violation == "review":
        result["review_status"] = "revise_supervisor"
    elif violation == "gap":
        result["answer_package"]["limitations"] = []
    elif violation == "computation":
        turn.require_computation = True
        result["research"]["computation_refs"] = ["unselected-computation"]
    elif violation == "injection":
        turn.forbidden_answer_text = ["CANARY_OVERRIDE_739"]
        result["answer"] += " canary_override_739"
    else:
        result["answer_package"]["claims"] = [
            {
                "claim_id": "claim-1",
                "statement": "Unsupported",
                "support": "direct",
                "evidence_ids": ["missing-source"],
                "source_task_ids": ["task-1"],
            }
        ]
    with pytest.raises(AssertionError):
        check_result(turn, state, result)
