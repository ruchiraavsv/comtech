from uuid import uuid4

import pytest
from ag_ui.core import CustomEvent, TextMessageContentEvent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import KnowledgeTask, Limits
from comtech.agents.graph import build_enterprise_graph, check_plan
from comtech.events import graph_events

from .helpers import FakeModel, FakeTools


async def test_parallel_workers_merge_and_new_turn_resets_evidence():
    tools, model = FakeTools(delay=0.03), FakeModel(tasks=2)
    graph = build_enterprise_graph(
        model, tools, TokenCounter(), Limits(parallel_workers=2), InMemorySaver()
    )
    config = {"configurable": {"thread_id": str(uuid4())}, "recursion_limit": 200}
    first = await graph.ainvoke({"messages": [HumanMessage(content="Who owns these?")]}, config)
    assert tools.peak == 2
    assert len(first["task_results"]) == len(first["evidence"]) == 2
    assert "[1]" in first["final_answer"] and "as of 2026-09-15" in first["final_answer"]
    second = await graph.ainvoke({"messages": [HumanMessage(content="And now?")]}, config)
    assert len(second["messages"]) == 4
    assert len(second["evidence"]) == 2
    assert not set(first["evidence"]).intersection(second["evidence"])
    assert second["review_cycle"] == 1
    assert "observations" not in second and "history" not in second


async def test_reviewer_rejection_cannot_reach_finalizer():
    model = FakeModel(reject=True)
    graph = build_enterprise_graph(model, FakeTools(), TokenCounter(), Limits())
    with pytest.raises(RuntimeError, match="Review limit"):
        await graph.ainvoke({"messages": [HumanMessage(content="Owner?")]})
    assert len([c for c in model.calls if c[0] == "review"]) == 2
    assert not any(c[0] == "final" for c in model.calls)


@pytest.mark.parametrize("persistent", [False, True])
async def test_final_wording_correction_streams_only_validated_message(persistent):
    class Wording(FakeModel):
        attempts = 0

        async def generate(self, role, payload, schema, maximum):
            value, usage = await super().generate(role, payload, schema, maximum)
            if role == "final":
                self.attempts += 1
                if self.attempts == 1 or persistent:
                    value.paragraphs[0].text += " EV-invalid-citation"
            return value, usage

    model = Wording()
    graph = build_enterprise_graph(model, FakeTools(), TokenCounter(), Limits(), InMemorySaver())
    events = []

    async def consume():
        async for event in graph_events(
            graph,
            {"messages": [HumanMessage(content="Owner?")]},
            {"configurable": {"thread_id": str(uuid4())}},
            uuid4(),
            uuid4(),
        ):
            events.append(event)

    await consume()
    content = [e.delta for e in events if isinstance(e, TextMessageContentEvent)]
    assert len(content) == 1
    assert all("EV-invalid" not in value for value in content)
    assert "Team A" in content[0]
    assert model.attempts == 2


async def test_only_approved_output_is_streamed_and_context_is_projected():
    model = FakeModel()
    graph = build_enterprise_graph(model, FakeTools(), TokenCounter(), Limits(), InMemorySaver())
    events = [
        e
        async for e in graph_events(
            graph,
            {"messages": [HumanMessage(content="Owner?")]},
            {"recursion_limit": 200, "configurable": {"thread_id": str(uuid4())}},
            uuid4(),
            uuid4(),
        )
    ]
    text = [e.delta for e in events if isinstance(e, TextMessageContentEvent)]
    assert len(text) == 1 and "Team A" in text[0]
    assert any(isinstance(e, CustomEvent) and e.name == "agent.activity" for e in events)
    for role, payload, _ in model.calls:
        if role in ("review", "final"):
            assert not {"messages", "plan", "observations", "history"}.intersection(payload)
        if role == "final":
            assert not {"task_results", "review_cycle"}.intersection(payload)


def test_plan_rejects_cycles_missing_dependencies_and_duplicate_ids():
    with pytest.raises(ValueError, match="Cyclic"):
        check_plan(
            [
                KnowledgeTask(task_id="a", objective="a", depends_on=["b"]),
                KnowledgeTask(task_id="b", objective="b", depends_on=["a"]),
            ],
            6,
        )
    with pytest.raises(ValueError, match="Unknown"):
        check_plan([KnowledgeTask(task_id="a", objective="a", depends_on=["b"])], 6)
    with pytest.raises(ValueError, match="identity"):
        check_plan([KnowledgeTask(task_id="a", objective="a")] * 2, 6)


async def test_checkpoint_resume_does_not_restart_worker_exploration():
    class InterruptedModel(FakeModel):
        failed_once = False

        async def generate(self, role, payload, schema, max_output_tokens):
            if role == "worker_finalize" and not self.failed_once:
                self.failed_once = True
                raise RuntimeError("Synthetic interruption before finalization")
            return await super().generate(role, payload, schema, max_output_tokens)

    model, tools = InterruptedModel(decisions=20), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits(), InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}, "recursion_limit": 200}
    with pytest.raises(RuntimeError, match="Synthetic interruption"):
        await graph.ainvoke({"messages": [HumanMessage(content="Owner?")]}, config)
    assert len(tools.calls) == 5
    snapshot = await graph.aget_state(config)
    assert snapshot.next
    output = await graph.ainvoke(None, config)
    assert len(tools.calls) == 5
    assert output["task_results"]["task-0"]["termination_reason"] == "cycle_limit"
    assert "inspected sections" in output["final_answer"]


async def test_targeted_research_repair_preserves_existing_evidence():
    from comtech.agents.contracts import ReviewDecision, SupervisorPlan

    class RepairModel(FakeModel):
        reviewed = 0

        async def generate(self, role, payload, schema, max_output_tokens):
            if role == "review":
                self.reviewed += 1
                if self.reviewed == 1:
                    return ReviewDecision(
                        status="revise_supervisor",
                        issues=[],
                        required_changes=["Resolve another service"],
                        followup_tasks=[
                            KnowledgeTask(task_id="followup", objective="Find another owner")
                        ],
                    ), {"input_tokens": 1, "output_tokens": 1}
            if role == "plan" and "existing_tasks" in payload:
                return SupervisorPlan(
                    resolved_request=payload["resolved_request"],
                    tasks=[KnowledgeTask(task_id="followup", objective="Find another owner")],
                ), {"input_tokens": 1, "output_tokens": 1}
            return await super().generate(role, payload, schema, max_output_tokens)

    model, tools = RepairModel(), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits())
    output = await graph.ainvoke(
        {"messages": [HumanMessage(content="Owners?")]}, {"recursion_limit": 200}
    )
    assert len(tools.calls) == 2 and output["review_cycle"] == 2
    assert set(output["task_results"]) == {"task-0", "followup"}
    assert len(output["evidence"]) == 2


@pytest.mark.parametrize("severity", ["SEV-1", "SEV-2", "SEV-3"])
async def test_incident_severity_is_not_invented_evidence_markup(severity):
    from comtech.agents.budget import digest

    class Incidents(FakeTools):
        async def call(self, name, arguments):
            result = await super().call(name, arguments)
            item = result.observations[0]
            item.content = f"The documented incident severity is {severity}."
            item.content_hash = digest(item.content)
            return result

    model = FakeModel()
    output = await build_enterprise_graph(model, Incidents(), TokenCounter(), Limits()).ainvoke(
        {"messages": [HumanMessage(content="Incident severity?")]}
    )
    assert severity in output["final_answer"]
    assert len([r for r, _, _ in model.calls if r == "final"]) == 1
