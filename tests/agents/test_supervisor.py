from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import (
    ClarificationRequest,
    KnowledgeTask,
    Limits,
    SupervisorAnswerPackage,
)
from comtech.agents.graph import build_enterprise_graph, build_legacy_graph
from comtech.research.contracts import DelegateAction, KnowledgeDelegation, SubmitAction

from .helpers import FakeModel, FakeTools


@pytest.mark.parametrize("persistent", [False, True])
async def test_missing_citation_selections_are_repaired_before_spending_a_review(persistent):
    class Repair(FakeModel):
        submissions = 0

        async def generate(self, role, payload, schema, maximum):
            value, usage = await super().generate(role, payload, schema, maximum)
            if role == "supervisor" and isinstance(value.decision, SubmitAction):
                self.submissions += 1
                if self.submissions == 2:
                    assert payload["rejected_answer_package"]
                    for claim in value.decision.answer.claims:
                        assert claim.claim_id in payload["validation_errors"][0]
                    assert "No evidence_ids selected" in payload["validation_errors"][0]
                if self.submissions == 1 or persistent:
                    for claim in value.decision.answer.claims:
                        claim.evidence_ids = []
            return value, usage

    model, tools = Repair(tasks=2), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits())
    if persistent:
        with pytest.raises(RuntimeError, match="validation failed after correction"):
            await graph.ainvoke({"messages": [HumanMessage(content="Owners?")]})
    else:
        result = await graph.ainvoke({"messages": [HumanMessage(content="Owners?")]})
        assert result["review_cycle"] == 1 and "Team A" in result["final_answer"]
    assert len(tools.calls) == 2 and model.submissions == 2
    assert len([r for r, _, _ in model.calls if r == "review"]) == (0 if persistent else 1)


async def test_supervisor_changes_next_objective_after_inspecting_a_result():
    class Adaptive(FakeModel):
        async def generate(self, role, payload, schema, max_output_tokens):
            if role == "supervisor" and set(payload["task_results"]) == {"task-0"}:
                assert "Team A" in payload["task_results"]["task-0"]["claims"][0]["statement"]
                return schema(
                    decision=DelegateAction(
                        resolved_request="Owner and its dependencies",
                        calls=[
                            KnowledgeDelegation(
                                task=KnowledgeTask(
                                    task_id="followup",
                                    objective="Investigate Team A dependencies",
                                    depends_on=["task-0"],
                                )
                            )
                        ],
                    )
                ), {}
            return await super().generate(role, payload, schema, max_output_tokens)

    model, tools = Adaptive(), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits())
    output = await graph.ainvoke({"messages": [HumanMessage(content="Owner and dependencies?")]})
    assert set(output["task_results"]) == {"task-0", "followup"}
    assert output["supervisor_turns"] == 3
    followup = [
        p for r, p, _ in model.calls if r == "decision" and p["task"]["task_id"] == "followup"
    ]
    assert "Team A" in followup[0]["task"]["context"]
    assert not any(role == "plan" for role, _, _ in model.calls)
    assert len(tools.calls) == 2
    review = next(p for r, p, _ in model.calls if r == "review")
    assert review["user_request"] == "Owner and dependencies?"


async def test_failed_worker_attribution_preserves_independent_validated_results():
    class BadWorker(FakeModel):
        async def generate(self, role, payload, schema, maximum):
            result, usage = await super().generate(role, payload, schema, maximum)
            if role == "worker_finalize" and payload["task"]["task_id"] == "task-0":
                result.claims[0].evidence[0].observation_id = "OBS-truncated"
            return result, usage

    model, tools = BadWorker(tasks=2), FakeTools()
    result = await build_enterprise_graph(model, tools, TokenCounter(), Limits()).ainvoke(
        {"messages": [HumanMessage(content="Owners?")]}
    )
    assert not result["task_results"]["task-0"]["claims"]
    assert result["task_results"]["task-0"]["unresolved"]
    assert result["task_results"]["task-1"]["claims"]
    assert "task-1 is owned by Team A" in result["final_answer"]
    assert "no findings from this task are validated" in result["final_answer"]
    assert len(tools.calls) == 2
    review = next(p for r, p, _ in model.calls if r == "review")
    assert "task-1:owner" in review["validated_premise_ids"]
    assert review["citation_plan"]["task-1:owner"]


async def test_clarification_can_submit_without_retrieval():
    class Clarify(FakeModel):
        async def generate(self, role, payload, schema, max_output_tokens):
            if role == "supervisor":
                return schema(
                    decision=SubmitAction(
                        answer=SupervisorAnswerPackage(
                            resolved_request="Which system?",
                            claims=[],
                            unresolved=[],
                            limitations=[],
                            source_conflicts=[],
                            clarification=ClarificationRequest(question="Which service?"),
                        )
                    )
                ), {}
            return await super().generate(role, payload, schema, max_output_tokens)

    tools = FakeTools()
    output = await build_enterprise_graph(Clarify(), tools, TokenCounter(), Limits()).ainvoke(
        {"messages": [HumanMessage(content="Who owns it?")]}
    )
    assert output["final_answer"] == "Which service?"
    assert not tools.calls


async def test_repeated_invalid_proposals_stop_without_executing_tools():
    class Invalid(FakeModel):
        async def generate(self, role, payload, schema, max_output_tokens):
            if role == "supervisor":
                return schema(
                    decision=DelegateAction(
                        resolved_request="Owner",
                        calls=[
                            KnowledgeDelegation(
                                task=KnowledgeTask(
                                    task_id="bad",
                                    objective="Owner",
                                    depends_on=["unknown"],
                                )
                            )
                        ],
                    )
                ), {}
            return await super().generate(role, payload, schema, max_output_tokens)

    tools = FakeTools()
    with pytest.raises(RuntimeError, match="Supervisor turn limit"):
        await build_enterprise_graph(Invalid(), tools, TokenCounter(), Limits()).ainvoke(
            {"messages": [HumanMessage(content="Owner?")]}, {"recursion_limit": 100}
        )
    assert not tools.calls


async def test_old_pending_checkpoint_resumes_on_legacy_then_next_turn_uses_v2():
    class Interrupted(FakeModel):
        failed = False

        async def generate(self, role, payload, schema, max_output_tokens):
            if role == "worker_finalize" and not self.failed:
                self.failed = True
                raise RuntimeError("Interrupt legacy worker")
            return await super().generate(role, payload, schema, max_output_tokens)

    model, tools, saver = Interrupted(), FakeTools(), InMemorySaver()
    config = {"configurable": {"thread_id": str(uuid4())}, "recursion_limit": 200}
    old = build_legacy_graph(model, tools, TokenCounter(), Limits(), saver)
    with pytest.raises(RuntimeError, match="Interrupt legacy"):
        await old.ainvoke({"messages": [HumanMessage(content="Owner?")]}, config)
    assert len(tools.calls) == 1
    current = build_enterprise_graph(model, tools, TokenCounter(), Limits(), saver)
    with pytest.raises(ValueError, match="Pending run"):
        await current.ainvoke({"messages": [HumanMessage(content="Overwrite?")]}, config)
    resumed = await current.ainvoke(None, config)
    assert "Team A" in resumed["final_answer"] and len(tools.calls) == 1
    assert not any(role == "supervisor" for role, _, _ in model.calls)
    fresh = await current.ainvoke({"messages": [HumanMessage(content="And now?")]}, config)
    assert fresh["graph_version"] == 2 and fresh["review_cycle"] == 1
    assert len(fresh["messages"]) == 4
    assert len([s async for s in current.aget_state_history(config, limit=3)]) == 3


async def test_unsupported_checkpoint_version_is_explicit():
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": str(uuid4())}}
    graph = build_enterprise_graph(FakeModel(), FakeTools(), TokenCounter(), Limits(), saver)
    await graph.current.aupdate_state(config, {"graph_version": 99}, as_node="begin")
    with pytest.raises(ValueError, match="Unsupported checkpoint graph version"):
        await graph.ainvoke(None, config)


@pytest.mark.parametrize(
    "kinds", [("document",), ("service_catalog",), ("document", "incident_record")]
)
async def test_source_routes_preserve_exact_provenance(kinds):
    class Sources(FakeTools):
        async def call(self, name, arguments):
            result = await super().call(name, arguments)
            number = int(arguments["id"].split("-")[-1])
            result.observations[0].source_ref.source_type = kinds[number]
            return result

    model, tools = FakeModel(tasks=len(kinds)), Sources()
    output = await build_enterprise_graph(model, tools, TokenCounter(), Limits()).ainvoke(
        {"messages": [HumanMessage(content="Resolve the synthetic objectives")]},
        {"recursion_limit": 200},
    )
    assert {e["source_ref"]["source_type"] for e in output["evidence"].values()} == set(kinds)
    for role, payload, _ in model.calls:
        if role == "supervisor":
            assert payload["available_specialists"] == ["knowledge_worker"]
    assert output["review_cycle"] == 1
    final = next(payload for role, payload, _ in model.calls if role == "final")
    assert "evidence" not in final
    assert final["answer_package"]["claims"]
    for index, evidence in enumerate(output["evidence"].values(), 1):
        source = evidence["source_ref"]
        assert (
            f"[{index}] {source['source_id']}, version {source['version']}"
            in output["final_answer"]
        )


@pytest.mark.parametrize("failure", ["citation", "omission", "attribution"])
@pytest.mark.parametrize("persistent", [False, True])
async def test_final_wording_correction_is_bounded_and_keeps_review(failure, persistent):
    class Wording(FakeModel):
        final_calls = 0

        async def generate(self, role, payload, schema, max_output_tokens):
            value, usage = await super().generate(role, payload, schema, max_output_tokens)
            if role == "final":
                self.final_calls += 1
                if self.final_calls == 2:
                    assert payload["validation_error"]
                    assert payload["rejected_draft"] is not None
                if self.final_calls == 1 or persistent:
                    if failure == "citation":
                        value.paragraphs[0].text += " [EV-invented]"
                    elif failure == "omission":
                        value.paragraphs = []
                    else:
                        value.paragraphs[0].claim_ids = ["invented-claim"]
            return value, usage

    model, tools = Wording(), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits())
    result = await graph.ainvoke({"messages": [HumanMessage(content="Owner?")]})
    assert "Team A" in result["final_answer"] and "EV-invented" not in result["final_answer"]
    assert result["review_cycle"] == 1
    assert result["final_fallback"] == persistent
    assert model.final_calls == 2 and len(tools.calls) == 1
    assert len([r for r, _, _ in model.calls if r == "review"]) == 1


@pytest.mark.parametrize("role_to_fail", ["supervisor", "decision"])
async def test_malformed_decision_returns_feedback_before_any_tool(role_to_fail):
    from comtech.agents.errors import InvalidModelOutput

    class Malformed(FakeModel):
        failed = False
        corrected = False

        async def generate(self, role, payload, schema, max_output_tokens):
            if role == role_to_fail and not self.failed:
                self.failed = True
                raise InvalidModelOutput("Invalid JSON: trailing characters")
            if role == role_to_fail and not self.corrected:
                feedback = payload.get("validation_errors") or payload.get("failures")
                assert "trailing characters" in str(feedback)
                self.corrected = True
            return await super().generate(role, payload, schema, max_output_tokens)

    model, tools = Malformed(decisions=2 if role_to_fail == "decision" else 1), FakeTools()
    result = await build_enterprise_graph(model, tools, TokenCounter(), Limits()).ainvoke(
        {"messages": [HumanMessage(content="Owner?")]}, {"recursion_limit": 100}
    )
    assert model.corrected and "Team A" in result["final_answer"]
    assert len(tools.calls) == 1


async def test_incomplete_budget_fallback_can_repair_without_reopening_exploration(monkeypatch):
    from comtech.agents.errors import InvalidModelOutput
    from comtech.research import accounting
    from comtech.research.ledger import BudgetExhausted

    original = accounting.generate
    submissions = []

    async def generate(model, role, payload, schema, maximum, *, final=False):
        if role == "supervisor" and payload["task_results"]:
            submissions.append(final)
            if len(submissions) == 1:
                raise BudgetExhausted()
            assert final and not payload["available_specialists"]
            if len(submissions) == 2:
                raise InvalidModelOutput("Submit a compact package")
            assert "compact package" in str(payload["validation_errors"])
        return await original(model, role, payload, schema, maximum, final=final)

    monkeypatch.setattr(accounting, "generate", generate)
    tools = FakeTools()
    result = await build_enterprise_graph(FakeModel(), tools, TokenCounter(), Limits()).ainvoke(
        {"messages": [HumanMessage(content="Owner?")]}
    )
    assert submissions == [False, True, True]
    assert result["exploration_closed"] and result["review_cycle"] == 1
    assert "Team A" in result["final_answer"] and len(tools.calls) == 1
