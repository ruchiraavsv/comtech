import asyncio

import pytest

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import (
    ClaimDraft,
    KnowledgeTask,
    KnowledgeWorkerDraftResult,
    Limits,
    Observation,
    Selection,
)
from comtech.agents.evidence import materialize
from comtech.agents.worker import build_worker

from .helpers import FakeModel, FakeTools


def invocation():
    return {
        "task": KnowledgeTask(task_id="task", objective="Find owner").model_dump(),
        "run_id": "run-1",
    }


async def test_worker_selects_only_observed_evidence_and_hides_draft():
    model, tools, counter = FakeModel(), FakeTools(), TokenCounter()
    output = await build_worker(model, tools, counter, Limits()).ainvoke(invocation())
    assert output["result"]["status"] == "answered"
    assert output["result"]["termination_reason"] == "completed"
    assert len(output["evidence"]) == 1
    claim = output["result"]["claims"][0]
    item = output["evidence"][claim["evidence"][0]["evidence_id"]]
    assert item["content"] == output["observations"][item["observation_id"]]["content"]
    assert model.calls[-1][0] == "worker_finalize"
    assert "tools" not in model.calls[-1][1]


async def test_fifth_tool_cycle_still_finalizes_and_duplicate_reads_deduplicate():
    model, tools = FakeModel(decisions=20), FakeTools()
    output = await build_worker(model, tools, TokenCounter(), Limits()).ainvoke(invocation())
    assert len(tools.calls) == 5
    assert output["cycle"] == 5
    assert output["result"]["termination_reason"] == "cycle_limit"
    assert len(output["observations"]) == len(output["evidence"]) == 1


async def test_prebudget_rejection_never_executes_tool_and_uses_finalizer():
    model, tools = FakeModel(input_size=24000), FakeTools()
    output = await build_worker(model, tools, TokenCounter(), Limits()).ainvoke(invocation())
    assert tools.calls == []
    assert output["exploration_closed"]
    assert output["result"]["termination_reason"] == "context_budget"
    assert output["result"]["status"] == "partial"
    assert not output["result"]["claims"]
    assert "inspected sections" in output["result"]["unresolved"][0]["details"]
    assert any(c[0] == "worker_finalize" for c in model.calls)


async def test_context_exhausted_before_decision_skips_decision_but_not_finalizer():
    model, tools = FakeModel(input_size=25999), FakeTools()
    output = await build_worker(model, tools, TokenCounter(), Limits()).ainvoke(invocation())
    assert output["cycle"] == 0 and not tools.calls
    assert [c[0] for c in model.calls] == ["worker_finalize"]


async def test_tool_outage_is_not_an_empty_success_or_invented_evidence():
    model, tools = FakeModel(), FakeTools(fail=True)
    output = await build_worker(model, tools, TokenCounter(), Limits()).ainvoke(invocation())
    assert output["result"]["tool_failures"][0]["code"] == "UNAVAILABLE"
    assert not output["evidence"] and not output["result"]["claims"]


async def test_fabricated_selected_observation_rejected():
    draft = KnowledgeWorkerDraftResult(
        status="answered",
        unresolved=[],
        claims=[
            ClaimDraft(
                claim_id="x",
                statement="Made up",
                support="direct",
                evidence=[Selection(observation_id="unobserved")],
            )
        ],
    )
    with pytest.raises(ValueError, match="not observed"):
        materialize(draft, {}, "r", "t", "completed", [])


async def test_observation_hash_corruption_rejected():
    result = await FakeTools().call("lookup", {})
    item = result.observations[0]
    draft = KnowledgeWorkerDraftResult(
        status="answered",
        unresolved=[],
        claims=[
            ClaimDraft(
                claim_id="x",
                statement="Team A",
                support="direct",
                evidence=[Selection(observation_id=item.observation_id)],
            )
        ],
    )
    corrupt = Observation.model_validate({**item.model_dump(), "content": "Different text"})
    with pytest.raises(ValueError, match="hash"):
        materialize(draft, {item.observation_id: corrupt}, "r", "t", "completed", [])


async def test_cancellation_propagates():
    tools = FakeTools(delay=30)
    graph = build_worker(FakeModel(), tools, TokenCounter(), Limits())
    task = asyncio.create_task(graph.ainvoke(invocation()))
    await tools.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert tools.active == 0


def test_invalid_budget_configuration():
    with pytest.raises(ValueError, match="exploration"):
        Limits(total_context_budget=5000, finalization_reserve=4000)


@pytest.mark.parametrize("over", [0, 1])
async def test_exact_tool_budget_boundary(over):
    from comtech.agents.contracts import Decision

    counter = TokenCounter()
    decision = Decision(action="tool", tool_name="lookup", arguments_json='{"id":"task"}')
    size = 26000 - counter.count(decision) - 3000 - 128 + over
    model, tools = FakeModel(input_size=size), FakeTools()
    output = await build_worker(model, tools, counter, Limits()).ainvoke(invocation())
    assert len(tools.calls) == (0 if over else 1)
    if over:
        assert output["termination_reason"] == "context_budget"


async def test_structural_draft_repair_uses_same_evidence_without_more_tools():
    class RepairModel(FakeModel):
        attempts = 0

        async def generate(self, role, payload, schema, max_output_tokens):
            value, usage = await super().generate(role, payload, schema, max_output_tokens)
            if role == "worker_finalize":
                self.attempts += 1
                if self.attempts == 1:
                    value.claims[0].evidence = []
                else:
                    assert "Claim lacks selected supporting evidence" in payload["validation_error"]
                    assert payload["rejected_draft"]["claims"][0]["evidence"] == []
                    assert payload["validation_issues"][0]["claim_id"] == "owner"
            return value, usage

    model, tools = RepairModel(), FakeTools()
    output = await build_worker(model, tools, TokenCounter(), Limits()).ainvoke(invocation())
    assert len(tools.calls) == 1 and model.attempts == 2
    assert output["result"]["status"] == "answered"


async def test_repeated_invalid_draft_stops_after_two_attempts():
    class InvalidModel(FakeModel):
        attempts = 0

        async def generate(self, role, payload, schema, max_output_tokens):
            value, usage = await super().generate(role, payload, schema, max_output_tokens)
            if role == "worker_finalize":
                self.attempts += 1
                value.claims[0].evidence = []
            return value, usage

    model, tools = InvalidModel(), FakeTools()
    with pytest.raises(ValueError, match="supporting evidence"):
        await build_worker(model, tools, TokenCounter(), Limits()).ainvoke(invocation())
    assert len(tools.calls) == 1 and model.attempts == 2


async def test_repair_identifies_all_missing_derived_fields_and_preserves_premise():
    class Repair(FakeModel):
        async def generate(self, role, payload, schema, maximum):
            value, usage = await super().generate(role, payload, schema, maximum)
            if role == "worker_finalize":
                if payload.get("validation_issues"):
                    assert {(i["claim_id"], i["field"]) for i in payload["validation_issues"]} == {
                        ("conclusion", "premise_claim_ids"),
                        ("conclusion", "derivation"),
                    }
                    value = schema.model_validate(payload["rejected_draft"])
                    value.claims[1].premise_claim_ids = ["owner"]
                    value.claims[1].derivation = "Use the documented owner for this service."
                else:
                    value.claims.append(
                        value.claims[0].model_copy(
                            update={"claim_id": "conclusion", "support": "derived"}
                        )
                    )
            return value, usage

    model, tools = Repair(), FakeTools()
    output = await build_worker(model, tools, TokenCounter(), Limits()).ainvoke(invocation())
    assert len(tools.calls) == 1
    assert output["result"]["claims"][1]["premise_claim_ids"] == ["task:owner"]
    assert len([c for c in model.calls if c[0] == "worker_finalize"]) == 2
