"""R5 acceptance: scripted semantics, real queue/ledger/broker/PostgreSQL checkpoints."""

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from comtech.research.accounting import bind
from comtech.research.actions import ChildProposal, ResearchLimits
from comtech.research.admission import Admission
from comtech.research.agent import ResearchAgent
from comtech.research.contracts import SpecialistResult
from comtech.research.ledger import BudgetExhausted, RunClosed
from comtech.research.python_execution import PythonExecutor
from comtech.research.queue import TaskQueue
from comtech.research.runner_client import RunnerClient

from .test_broker import bundle as bundle

pytestmark = pytest.mark.integration


def proposal(b, description="Establish commit ordering", partition="root", **kwargs):
    return ChildProposal(
        description=description,
        expected_output="Supported finding",
        analysis_mode="semantic",
        narrowed_scope=b.scope,
        partition=partition,
        gap=description,
        reason="Required fact",
        expected_information_gain="Resolve fact",
        **kwargs,
    )


class Script:
    context_window = 30000

    def __init__(self, callback, counter):
        self.callback, self.counter, self.calls = callback, counter, []

    def input_size(self, role, payload, schema):
        return self.counter.count(payload) + self.counter.count(schema.model_json_schema()) + 200

    async def generate(self, role, payload, schema, maximum):
        self.calls.append((role, payload))
        value = self.callback(role, payload)
        return schema.model_validate(value), {"input_tokens": 500, "output_tokens": 100}


def draft(payload, *, inherited=False):
    claims = []
    ids = list(payload["child_claims"]) if inherited else []
    if not inherited and payload["evidence"]:
        evidence = next(iter(payload["evidence"]))
        claims = [
            {
                "claim_id": "fact",
                "statement": "Alpha commits before dispatch.",
                "support": "direct",
                "evidence": [{"evidence_id": evidence, "role": "support"}],
            }
        ]
    return {
        "status": "answered" if claims or ids else "partial",
        "claims": claims,
        "inherited_claim_ids": ids,
        "unresolved": []
        if claims or ids
        else [
            {
                "information_need": "Commit ordering",
                "reason": "insufficient_evidence",
                "details": f"Inspection did not establish it; {payload['termination_reason']}.",
            }
        ],
    }


async def setup(b, callback, *, limits=None, python=None, mode="semantic"):
    queue = TaskQueue(b.caps.pool)
    admission = Admission(queue, limits)
    (root,) = await admission.propose(
        b.ctx.lease, [proposal(b).model_copy(update={"analysis_mode": mode})]
    )
    claim = await queue.claim(uuid4(), ["research"])
    assert claim.task["id"] == root
    ctx = replace(b.ctx, lease=claim.lease, scope=claim.task["scope_key"])
    saver = AsyncPostgresSaver(b.caps.pool)
    await saver.setup()
    model = Script(callback, b.broker.counter)
    agent = ResearchAgent(model, b.broker, python, queue, saver, limits)
    return queue, claim, ctx, model, agent


async def invoke(agent, claim, ctx, queue):
    with bind(ctx):
        outcome = await agent(claim)
    await queue.transition(
        claim.lease,
        state=outcome.state,
        result=outcome.result,
        dependencies=outcome.dependencies,
        continuation=outcome.continuation,
        reason=outcome.reason,
    )
    return outcome


async def test_direct_early_answer_and_durable_replay(bundle):
    b = bundle

    def response(role, payload):
        assert payload["user_request"] == "Synthetic budget test"
        if role == "research":
            read = payload["tools"]["read_document_sections"]["parameters"]["properties"]
            assert read["max_sections"]["maximum"] == 3
        if role == "research_finalize":
            return draft(payload)
        return {
            "decision": {"action": "finalize"}
            if payload["evidence"]
            else {
                "action": "knowledge_search",
                "arguments": {"query": "commit", "service_ids": ["svc-0"]},
            }
        }

    queue, claim, ctx, model, agent = await setup(b, response)
    with bind(ctx):
        first = await agent(claim)
        # Committed graph result before queue transition: restarted handler reuses it.
        again = await agent(claim)
    assert first == again and len(model.calls) == 3
    envelope = SpecialistResult.model_validate(first.result)
    assert envelope.result.status == "answered" and len(b.embeddings) == 1
    assert all(e.task_id == str(claim.task["id"]) for e in envelope.evidence.values())
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["data_requests"]["used"] == 1 and counts["python_executions"]["used"] == 0
    await queue.transition(claim.lease, state="completed", result=first.result)


async def test_research_can_navigate_exact_omitted_section_ids(bundle):
    b = bundle

    def response(role, payload):
        if role == "research_finalize":
            return draft(payload)
        if not payload["evidence"]:
            args = {"document_id": "DOC-0", "query": "commit", "max_sections": 1}
        elif len(payload["evidence"]) == 1:
            options = payload["last_result"]["section_options"]
            assert options == [{"section_id": "DOC-0:v1:s1", "title": "Section 1"}]
            args = {
                "document_id": "DOC-0",
                "query": "alpha",
                "section_ids": [options[0]["section_id"]],
            }
        else:
            return {"decision": {"action": "finalize"}}
        return {"decision": {"action": "read_document_sections", "arguments": args}}

    queue, claim, ctx, model, agent = await setup(b, response)
    result = await invoke(agent, claim, ctx, queue)
    assert result.result["result"]["status"] == "answered"
    assert len([r for r, _ in model.calls if r == "research"]) == 3


async def test_recursive_child_inheritance_and_unused_retirement(bundle):
    b = bundle

    def response(role, payload):
        if role == "research_finalize":
            return draft(payload, inherited=bool(payload["child_claims"]))
        if payload["child_claims"] or payload["evidence"]:
            action = {"action": "finalize"}
        elif payload["task"]["depth"] == 0:
            action = {
                "action": "delegate",
                "children": [
                    proposal(b, "Inspect Alpha", "alpha").model_dump(mode="json"),
                    proposal(b, "Optional alternative", "optional").model_dump(mode="json"),
                ],
            }
        else:
            action = {
                "action": "read_document_sections",
                "arguments": {"document_id": "DOC-0", "query": "commit"},
            }
        return {"decision": action}

    queue, root, ctx, model, agent = await setup(b, response)
    waiting = await invoke(agent, root, ctx, queue)
    assert waiting.state == "waiting_children"
    child = await queue.claim(uuid4(), ["research"])
    await invoke(
        agent, child, replace(ctx, lease=child.lease, scope=child.task["scope_key"]), queue
    )
    resumed = await queue.claim(uuid4(), ["research"])
    assert resumed.task["id"] == root.task["id"]
    result = await invoke(agent, resumed, replace(ctx, lease=resumed.lease), queue)
    envelope = SpecialistResult.model_validate(result.result)
    assert envelope.result.status == "answered"
    assert all(e.task_id == str(child.task["id"]) for e in envelope.evidence.values())
    other = next(i for i in waiting.dependencies if i != str(child.task["id"]))
    assert (await queue.get(other))["termination_reason"] == "unneeded"
    assert len([c for c in model.calls if c[0] == "research_finalize"]) == 2


@pytest.mark.parametrize("cause", ["unavailable", "repeat", "cycle_limit", "depth_limit"])
async def test_deterministic_stop_has_llm_partial_finalization(bundle, cause):
    b = bundle

    def response(role, payload):
        if role == "research_finalize":
            # No negative claim inferred from failed/repeated exploration.
            return {**draft({**payload, "evidence": {}}), "claims": []}
        if cause == "unavailable":
            action = {
                "action": "execute_python",
                "code": "result = 1",
                "purpose": "test",
                "input_refs": [],
            }
        elif cause == "depth_limit":
            action = {
                "action": "delegate",
                "children": [proposal(b, "child", "child").model_dump(mode="json")],
            }
        else:
            action = {
                "action": "read_document_sections",
                "arguments": {"document_id": "DOC-0", "query": "commit"},
            }
        return {"decision": action}

    limits = ResearchLimits(
        max_steps=1 if cause == "cycle_limit" else 5, max_depth=0 if cause == "depth_limit" else 4
    )
    queue, claim, ctx, model, agent = await setup(b, response, limits=limits)
    output = await invoke(agent, claim, ctx, queue)
    result = SpecialistResult.model_validate(output.result).result
    assert result.status == "partial"
    assert (
        result.termination_reason
        == {
            "unavailable": "no_progress",
            "repeat": "no_progress",
            "cycle_limit": "cycle_limit",
            "depth_limit": "depth_limit",
        }[cause]
    )
    assert model.calls[-1][0] == "research_finalize"


async def test_admission_dedupe_scope_cycles_and_cancel(bundle):
    b = bundle
    queue, root, ctx, _, _ = await setup(b, lambda *_: None)
    admission = Admission(queue)
    p = proposal(b, "child", "child")
    first = await admission.propose(ctx.lease, [p])
    assert first == await admission.propose(
        ctx.lease, [p.model_copy(update={"reason": "paraphrase"})]
    )
    queue.per_run = 3  # Keep both ancestors live for this wait-cycle boundary check.
    child = await queue.claim(uuid4(), ["research"])
    with pytest.raises(ValueError, match="cycle"):
        await admission.propose(child.lease, [proposal(b)])
    expanded = p.model_copy(
        update={"narrowed_scope": b.scope.model_copy(update={"sources": ["mcp"]})}
    )
    with pytest.raises(ValueError):
        await admission.propose(ctx.lease, [expanded])
    await queue.transition(root.lease, state="completed", result={"internal_test": True})
    with pytest.raises(RunClosed):
        await ctx.ledger.check(child.lease)
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["research_tasks"]["used"] == 2


async def test_admission_protects_finalization_capacity(bundle):
    b = bundle
    queue, _, ctx, _, _ = await setup(b, lambda *_: None)
    with pytest.raises(BudgetExhausted):
        await Admission(queue).propose(ctx.lease, [proposal(b, str(n), str(n)) for n in range(4)])
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["research_tasks"]["used"] == 1  # Whole batch rolled back.


async def test_unaffordable_child_batch_can_continue_with_a_bounded_direct_read(bundle):
    b = bundle

    def response(role, payload):
        if role == "research_finalize":
            return draft(payload)
        if payload["evidence"]:
            return {"decision": {"action": "finalize"}}
        if payload["failures"]:
            assert payload["failures"][-1]["code"] == "BUDGET_NOT_ADMITTED"
            return {
                "decision": {
                    "action": "read_document_sections",
                    "arguments": {"document_id": "DOC-0", "query": "commit"},
                }
            }
        return {
            "decision": {
                "action": "delegate",
                "children": [proposal(b, str(n), str(n)).model_dump(mode="json") for n in range(4)],
            }
        }

    queue, claim, ctx, model, agent = await setup(b, response)
    result = await invoke(agent, claim, ctx, queue)
    assert result.result["result"]["status"] == "answered"
    counters = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counters["research_tasks"]["used"] == counters["data_requests"]["used"] == 1
    assert counters["model_requests"]["used"] == 4


async def test_document_selectors_do_not_grant_inputs_or_expand_parent_scope(bundle):
    from types import SimpleNamespace

    from comtech.research.broker_contracts import BrokerError
    from comtech.research.contracts import ResearchRequest
    from comtech.research.specialist import ResearchSpecialist

    b = bundle
    queue = TaskQueue(b.caps.pool)
    specialist = ResearchSpecialist(SimpleNamespace(broker=b.broker, admission=Admission(queue)))
    request = ResearchRequest(
        task_id="r1",
        objective="Inspect Alpha",
        analysis_mode="semantic",
        expected_output="Supported finding",
        document_ids=["0"],
    )
    with bind(b.ctx):
        with pytest.raises(ValueError, match="Unrecognized document_ids"):
            await specialist.admit(request.model_copy(update={"document_ids": ["missing"]}))
        with pytest.raises(ValueError, match="registered references"):
            await specialist.admit(request.model_copy(update={"input_refs": ["DOC-0"]}))
        root = await specialist.admit(request)
    task = await queue.get(root)
    assert task["input"]["narrowed_scope"]["document_ids"] == ["DOC-0"]
    assert task["input"]["input_refs"] == []
    child = await queue.claim(uuid4(), ["research"])
    broadened = proposal(b, "Other document", "other").model_copy(
        update={"narrowed_scope": b.scope.model_copy(update={"document_ids": ["DOC-1"]})}
    )
    with pytest.raises(BrokerError, match="Expanded document_ids"):
        await Admission(queue).propose(child.lease, [broadened])
    assert (await b.ctx.ledger.counters(b.ctx.lease.objective_id))["research_tasks"]["used"] == 1


@pytest.mark.parametrize("persistent", [False, True])
async def test_malformed_research_proposal_recovers_or_finalizes_within_step_limit(
    bundle, persistent
):
    from comtech.agents.errors import InvalidModelOutput

    def response(role, payload):
        if role == "research_finalize":
            return draft(payload)
        if not payload["failures"] or persistent:
            raise InvalidModelOutput("Child narrowed_scope.fields is required")
        assert "narrowed_scope.fields" in payload["failures"][0]["message"]
        return {
            "decision": {"action": "finalize"}
            if payload["evidence"]
            else {
                "action": "read_document_sections",
                "arguments": {"document_id": "DOC-0", "query": "commit"},
            }
        }

    queue, claim, ctx, model, agent = await setup(bundle, response)
    result = await invoke(agent, claim, ctx, queue)
    envelope = SpecialistResult.model_validate(result.result)
    assert envelope.result.status == ("partial" if persistent else "answered")
    assert len(model.calls) == (3 if persistent else 4)
    if persistent:
        assert envelope.result.termination_reason == "no_progress"
    assert (await ctx.ledger.counters(ctx.lease.objective_id))["research_tasks"]["used"] == 1


async def test_shared_dependency_survives_until_last_parent_and_settles_late_usage(bundle):
    b = bundle
    limits = ResearchLimits(context_tokens=8000)
    queue, root, ctx, _, _ = await setup(b, lambda *_: None, limits=limits)
    queue.per_run = 4
    admission = Admission(queue, limits)
    (second_id,) = await admission.propose(b.ctx.lease, [proposal(b, "second root", "second")])
    second = await queue.claim(uuid4(), ["research"])
    assert second.task["id"] == second_id
    shared = proposal(b, "shared useful gap", "shared")
    (shared_id,) = await admission.propose(root.lease, [shared])
    assert (shared_id,) == await admission.propose(second.lease, [shared])
    child = await queue.claim(uuid4(), ["research"])
    with pytest.raises(ValueError, match="cycle"):
        await admission.propose(child.lease, [proposal(b, "second root", "second")])
    reservation = await ctx.ledger.reserve(
        child.lease, "late-call", {"model_requests": 1}, scope=child.task["scope_key"]
    )
    await ctx.ledger.start(child.lease, reservation)
    await queue.transition(root.lease, state="completed", result={"internal_test": True})
    assert (await queue.get(shared_id))["state"] == "running"
    await queue.transition(second.lease, state="completed", result={"internal_test": True})
    assert (await queue.get(shared_id))["state"] == "cancelled"
    with pytest.raises(RunClosed):
        await queue.transition(child.lease, state="completed", result={"late": True})
    await ctx.ledger.settle(reservation, {"model_requests": 1})
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["model_requests"]["used"] == 1
    async with b.caps.pool.connection() as conn:
        hold = await (
            await conn.execute(
                "SELECT closed FROM research_budget_holds WHERE objective_id=%s AND scope_key=%s",
                (ctx.lease.objective_id, child.task["scope_key"]),
            )
        ).fetchone()
    assert hold["closed"]


async def test_checkpoint_resume_after_interrupted_tool_does_not_repeat_external_call(bundle):
    from comtech.research.control import Control
    from comtech.research.delivery import Delivery

    b = bundle

    def response(role, payload):
        if role == "research_finalize":
            return draft(payload)
        return {
            "decision": {"action": "finalize"}
            if payload["evidence"]
            else {
                "action": "knowledge_search",
                "arguments": {"query": "commit", "service_ids": ["svc-0"]},
            }
        }

    queue, claim, ctx, model, agent = await setup(b, response)
    original = b.broker.call
    crashed = False

    async def cut_after_receipt(*args, **kwargs):
        nonlocal crashed
        result = await original(*args, **kwargs)
        if not crashed:
            crashed = True
            raise OSError("Synthetic process cut after durable broker receipt")
        return result

    b.broker.call = cut_after_receipt
    with bind(ctx), pytest.raises(OSError):
        await agent(claim)
    before = await ctx.ledger.counters(ctx.lease.objective_id)
    await Control(b.caps.pool, Delivery(b.caps.pool)).recover(b.scope.pinned_versions)
    resumed = await queue.claim(uuid4(), ["research"])
    output = await invoke(agent, resumed, replace(ctx, lease=resumed.lease), queue)
    after = await ctx.ledger.counters(ctx.lease.objective_id)
    assert (
        len(b.embeddings) == 1 and after["data_requests"]["used"] == before["data_requests"]["used"]
    )
    assert SpecialistResult.model_validate(output.result).result.status == "answered"


async def test_failed_child_can_finalize_partial_without_fabricating_absence(bundle):
    b = bundle

    def response(role, payload):
        if role == "research_finalize":
            return draft(payload)
        if payload["failures"]:
            return {"decision": {"action": "finalize"}}
        return {
            "decision": {
                "action": "delegate",
                "children": [proposal(b, "needed child", "needed").model_dump(mode="json")],
            }
        }

    queue, root, ctx, model, agent = await setup(b, response)
    await invoke(agent, root, ctx, queue)
    child = await queue.claim(uuid4(), ["research"])
    await queue.transition(child.lease, state="failed", reason="source_unavailable")
    parent = await queue.claim(uuid4(), ["research"])
    result = await invoke(agent, parent, replace(ctx, lease=parent.lease), queue)
    result = SpecialistResult.model_validate(result.result).result
    assert result.status == "partial" and not result.claims and result.tool_failures
    assert model.calls[-1][0] == "research_finalize"


@pytest.mark.parametrize("reason", ["context_budget", "deadline", "objective_budget"])
async def test_preflight_stop_preserves_tool_free_semantic_finalization(bundle, reason):
    b = bundle

    def response(role, payload):
        assert role == "research_finalize"
        assert payload["termination_reason"] == reason
        return draft(payload)

    queue, claim, ctx, model, agent = await setup(b, response)
    if reason == "context_budget":
        original = model.input_size
        model.input_size = lambda role, payload, schema: (
            24000 if role == "research" else original(role, payload, schema)
        )
    else:
        async with b.caps.pool.connection() as conn:
            if reason == "deadline":
                await conn.execute(
                    "UPDATE research_objectives SET created_at=clock_timestamp()-interval '1 hour',"
                    "exploration_deadline="
                    "clock_timestamp()-interval '1 second' WHERE id=%s",
                    (ctx.lease.objective_id,),
                )
            else:
                await conn.execute(
                    "UPDATE research_budget_counters SET ceiling=protected "
                    "WHERE objective_id=%s AND metric='model_tokens'",
                    (ctx.lease.objective_id,),
                )
    output = await invoke(agent, claim, ctx, queue)
    result = SpecialistResult.model_validate(output.result).result
    assert result.status == "partial" and result.termination_reason == reason
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["data_requests"]["used"] == counts["python_executions"]["used"] == 0
    assert counts["model_requests"]["used"] == 1


@pytest.mark.skipif(os.getenv("RUN_RUNNER_TESTS") != "1", reason="Requires isolated runner")
@pytest.mark.parametrize("mode", ["deterministic", "mixed"])
async def test_calculation_with_registered_artifact_and_unknowns(bundle, mode):
    from .test_runner import ready

    b = bundle
    client = RunnerClient(os.environ["RESEARCH_RUNNER_SOCKET"])
    info = await ready(client)
    executor = PythonExecutor(b.broker, client, info["environment_digest"])

    def response(role, payload):
        if role == "research_finalize":
            artifact = next(k for k in payload["artifacts"] if k.startswith("ART-"))
            return {
                "status": "answered",
                "claims": [
                    {
                        "claim_id": "calculation",
                        "statement": "Of two selected classifications, one matched; one is unknown."
                        if mode == "mixed"
                        else "The selected spans have a positive combined character length.",
                        "support": "derived",
                        "evidence": [],
                        "computation_ref": artifact,
                        "derivation": "Sum over registered inputs with limited coverage.",
                    }
                ],
                "unresolved": [],
            }
        if any(k.startswith("ART-") for k in payload["artifacts"]):
            return {"decision": {"action": "finalize"}}
        if not payload["evidence"]:
            return {
                "decision": {
                    "action": "read_document_sections",
                    "arguments": {"document_id": "DOC-0", "query": "commit"},
                }
            }
        refs = list(payload["evidence"])
        if mode == "mixed":
            # Scripted semantic extraction with original spans; Python only reduces the labels.
            code = """
import pandas as pd
rows = [{'event_id':'A','classification':'match','support':input_refs[0]},
        {'event_id':'B','classification':'unknown','support':input_refs[0]}]
counts = pd.DataFrame(rows).drop_duplicates('event_id')['classification'].value_counts()
value = {'match':int(counts.get('match',0)), 'unknown':int(counts.get('unknown',0)),
         'classified_inputs':rows, 'population_complete':False}
artifact = data.write_artifact(value, 'json', input_refs,
    method='Count scripted semantic labels after event identity deduplication', units='events',
    assumptions=['Unknown is not zero', 'Only selected classifications, not the corpus'],
    extraction_version='research-v1/scripted-semantic-fixture')
result = {'artifact_ref':artifact['artifact_ref'], 'counts':value}
"""
        else:
            code = """
import numpy as np
read = data.read_document_sections('DOC-0', 'commit')
length = int(np.sum([len(o['content']) for o in read['observations']]))
artifact = data.write_artifact({'length':length}, 'json',
    [o['observation_id'] for o in read['observations']],
    method='Sum selected span character lengths', units='characters',
    assumptions=['Selected returned spans only'])
result = {'artifact_ref':artifact['artifact_ref'], 'length':length}
"""
        return {
            "decision": {
                "action": "execute_python",
                "code": code,
                "purpose": "Calculate over identified inputs",
                "input_refs": refs,
            }
        }

    queue, claim, ctx, model, agent = await setup(b, response, python=executor, mode=mode)
    outcome = await invoke(agent, claim, ctx, queue)
    result = SpecialistResult.model_validate(outcome.result)
    assert len(result.artifact_refs) == len(result.execution_refs) == 1
    assert result.evidence and result.result.claims[0].support == "derived"
    final = model.calls[-1][1]
    record = final["artifacts"][result.artifact_refs[0]]
    assert record["manifest"]["analysis_provenance"] == {
        "prompt_version": "research-v1",
        "model": "Script",
        "decision_step": "2",
        "analysis_mode": mode,
    }
    assert record["coverage"]["method"] == "aggregate"
    assert "no inferred population" in record["coverage"]["relevant_omissions"][0]
    if mode == "mixed":
        assert '"unknown":1' in record["result"]
        assert record["manifest"]["extraction_version"] == "research-v1/scripted-semantic-fixture"
    await ready(client)


@pytest.mark.parametrize("reject", [False, True, "repair", "failed_repair", "admission"])
async def test_supervisor_background_wait_review_and_final_only_publication(bundle, reject):
    from comtech.agents.contracts import Limits
    from comtech.agents.supervisor import build_supervisor_graph
    from comtech.research.background import BackgroundGraph
    from comtech.research.delivery import Delivery
    from comtech.research.queue import Claim
    from comtech.research.specialist import ResearchSpecialist

    b = bundle
    review_calls = []
    admission_feedback = []

    def response(role, payload):
        if role in ("supervisor", "review") and payload.get("task_results"):
            assert payload["evidence"]
            for result in payload["task_results"].values():
                assert result["specialist"] == "research"
                assert "evidence" not in result
        if role == "supervisor":
            if reject == "admission" and payload["validation_errors"]:
                admission_feedback.extend(payload["validation_errors"])
                assert not payload["delegated_tasks"]
            repair = (
                reject in ("repair", "failed_repair")
                and review_calls
                and "r2" not in payload["task_results"]
            )
            if not payload["task_results"] or repair:
                assert "research" in payload["available_specialists"]
                return {
                    "decision": {
                        "action": "delegate",
                        "resolved_request": "Ordering",
                        "calls": [
                            {
                                "specialist": "research",
                                "task": {
                                    "task_id": "r2" if repair else "r1",
                                    "objective": "Establish commit ordering",
                                    "analysis_mode": "semantic",
                                    "expected_output": "Supported fact",
                                    "document_ids": ["DOC-0"],
                                    "input_refs": ["DOC-0"]
                                    if reject == "admission" and not admission_feedback
                                    else [],
                                },
                            }
                        ],
                    }
                }
            failed = payload["task_results"].get("r2", {}).get("result", {}).get("tool_failures")
            if failed:
                assert reject == "failed_repair"
                assert not payload["task_results"]["r2"]["result"]["claims"]
                assert "without a validated result" in failed[0]["message"]
            selected = "r2" if "r2" in payload["task_results"] and not failed else "r1"
            result = payload["task_results"][selected]["result"]
            claim = result["claims"][0]
            return {
                "decision": {
                    "action": "submit",
                    "answer": {
                        "resolved_request": "Ordering",
                        "claims": [
                            {
                                "claim_id": claim["claim_id"],
                                "statement": claim["statement"],
                                "support": claim["support"],
                                "evidence_ids": [e["evidence_id"] for e in claim["evidence"]],
                                "source_task_ids": [selected],
                            }
                        ],
                        "unresolved": [],
                        "limitations": [
                            "The follow-up research failed; this assessment uses the earlier "
                            "validated findings."
                        ]
                        if failed
                        else [],
                        "source_conflicts": [],
                        "clarification": None,
                    },
                }
            }
        if role == "research":
            return {
                "decision": {"action": "finalize"}
                if payload["evidence"]
                else {
                    "action": "read_document_sections",
                    "arguments": {"document_id": "DOC-0", "query": "commit"},
                }
            }
        if role == "research_finalize":
            return draft(payload)
        if role == "review":
            review_calls.append(role)
            revise = reject is True or (
                reject in ("repair", "failed_repair") and len(review_calls) == 1
            )
            return {
                "status": "revise_supervisor" if revise else "approved",
                "issues": [],
                "required_changes": ["Verify the required ordering in targeted source context"]
                if revise
                else [],
                "followup_tasks": [],
            }
        assert role == "final" and reject is not True
        assert "evidence" not in payload
        return {
            "paragraphs": [
                {
                    "text": "Alpha commits before dispatch.",
                    "claim_ids": [payload["answer_package"]["claims"][0]["claim_id"]],
                }
            ]
        }

    saver = AsyncPostgresSaver(b.caps.pool)
    await saver.setup()
    queue = TaskQueue(b.caps.pool)
    model = Script(response, b.broker.counter)
    agent = ResearchAgent(model, b.broker, None, queue, saver)
    graph = build_supervisor_graph(
        model, b.broker.tools, b.broker.counter, Limits(), saver, research=ResearchSpecialist(agent)
    )
    handler = BackgroundGraph(graph, Delivery(b.caps.pool), b.scope.pinned_versions)
    task = await queue.get(b.ctx.lease.task_id)
    objective = await b.ctx.ledger.check(b.ctx.lease)
    claim = Claim(b.ctx.lease, task, objective, [])
    waiting = await invoke(handler, claim, b.ctx, queue)
    assert waiting.state == "waiting_children"
    if reject == "admission":
        assert len(admission_feedback) == 1 and "registered references" in admission_feedback[0]
        counts = await b.ctx.ledger.counters(b.ctx.lease.objective_id)
        assert counts["research_tasks"]["used"] == counts["specialist_calls"]["used"] == 1
    child = await queue.claim(uuid4(), ["research"])
    await invoke(
        agent, child, replace(b.ctx, lease=child.lease, scope=child.task["scope_key"]), queue
    )
    parent = await queue.claim(uuid4(), ["supervisor"])
    with bind(replace(b.ctx, lease=parent.lease)):
        if reject is True:
            with pytest.raises(RuntimeError, match="Review limit"):
                await handler(parent)
            assert len(review_calls) == 2
        else:
            result = await handler(parent)
            if reject in ("repair", "failed_repair"):
                assert result.state == "waiting_children"
                await queue.transition(
                    parent.lease,
                    state=result.state,
                    dependencies=result.dependencies,
                    continuation=result.continuation,
                )
                repair_child = await queue.claim(uuid4(), ["research"])
                if reject == "failed_repair":
                    await queue.transition(
                        repair_child.lease,
                        state="failed",
                        reason="ClaimValidationError",
                        result={"claims": [{"statement": "Unvalidated follow-up content"}]},
                    )
                else:
                    await invoke(
                        agent,
                        repair_child,
                        replace(
                            b.ctx, lease=repair_child.lease, scope=repair_child.task["scope_key"]
                        ),
                        queue,
                    )
                repaired_parent = await queue.claim(uuid4(), ["supervisor"])
                with bind(replace(b.ctx, lease=repaired_parent.lease)):
                    result = await handler(repaired_parent)
                counts = await b.ctx.ledger.counters(b.ctx.lease.objective_id)
                assert counts["research_tasks"]["used"] == counts["specialist_calls"]["used"] == 2
            assert result.result["review_status"] == "approved"
            assert "Alpha commits" in result.result["answer"]
            assert len(review_calls) == (2 if reject in ("repair", "failed_repair") else 1)
            if reject == "failed_repair":
                assert "follow-up research failed" in result.result["answer"]
                assert "Unvalidated follow-up content" not in result.result["answer"]
    async with b.caps.pool.connection() as conn:
        events = await (
            await conn.execute("SELECT payload FROM app_run_events WHERE run_id=%s", (b.run["id"],))
        ).fetchall()
    assert not any(e["payload"]["type"] == "TEXT_MESSAGE_CONTENT" for e in events)


@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("defect", ["evidence", "claim_id", "inherited_claim_ids"])
async def test_research_claim_repair_is_bounded_and_reuses_observations(bundle, persistent, defect):
    def response(role, payload):
        if role == "research_finalize":
            value = draft(payload)
            if payload.get("validation_issues"):
                assert payload["rejected_draft"]
                assert payload["validation_issues"][0]["field"] == defect
            if persistent or not payload.get("validation_issues"):
                if defect == "evidence":
                    value["claims"][0]["evidence"] = []
                elif defect == "claim_id":
                    value["claims"][0]["claim_id"] = "objective/child/claim"
                else:
                    value["inherited_claim_ids"] = ["unregistered-child-claim"]
            return value
        return {
            "decision": {"action": "finalize"}
            if payload["evidence"]
            else {
                "action": "read_document_sections",
                "arguments": {"document_id": "DOC-0", "query": "commit"},
            }
        }

    queue, claim, ctx, model, agent = await setup(bundle, response)
    if persistent:
        from comtech.agents.errors import ClaimValidationError

        with pytest.raises(ClaimValidationError):
            await invoke(agent, claim, ctx, queue)
    else:
        outcome = await invoke(agent, claim, ctx, queue)
        assert outcome.result["result"]["status"] == "answered"
    assert len([r for r, _ in model.calls if r == "research_finalize"]) == 2
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["data_requests"]["used"] == 1


@pytest.mark.skipif(os.getenv("RUN_RUNNER_TESTS") != "1", reason="Requires isolated runner")
async def test_metadata_discovery_preserves_context_and_reaches_calculation(bundle):
    from .test_runner import ready

    b = bundle
    for i in range(3, 132):
        b.store.documents[f"DOC-{i}"] = {**b.store.documents["DOC-0"], "document_id": f"DOC-{i}"}
    client = RunnerClient(os.environ["RESEARCH_RUNNER_SOCKET"])
    info = await ready(client)
    executor = PythonExecutor(b.broker, client, info["environment_digest"])
    codes = [
        "result = data.describe()",
        "p = data.enumerate_documents({'limit':1000}); result = {'rows':len(p['items'])}",
        "p = data.enumerate_documents({'limit':1000}); "
        "a = data.write_artifact({'total':len(p['items'])}, 'json', list(data.receipt_refs), "
        "method='Count the fully enumerated version metadata'); "
        "result = {'artifact_ref':a['artifact_ref']}",
    ]

    def response(role, payload):
        assert not any(k.startswith("DOC-") for k in payload["artifacts"])
        assert b.broker.counter.count(payload) < 16000
        if role == "research":
            assert "total_count" in payload["sdk_results"]["enumerate_documents"]["coverage"]
            assert "total_count" not in payload["sdk_results"]["enumerate_documents"]
            assert payload["sdk_schemas"]["enumerate_documents"]["properties"]["version_policy"][
                "enum"
            ] == ["pinned"]
            assert (
                payload["sdk_schemas"]["read_document_sections"]["properties"]["max_sections"][
                    "maximum"
                ]
                == 3
            )
        artifacts = [k for k in payload["artifacts"] if k.startswith("ART-")]
        if role == "research_finalize":
            assert artifacts, payload["termination_reason"]
            return {
                "status": "answered",
                "unresolved": [],
                "claims": [
                    {
                        "claim_id": "count",
                        "statement": "The release contains 132 document versions.",
                        "support": "derived",
                        "evidence": [],
                        "computation_ref": artifacts[0],
                        "derivation": "Count all enumerated version metadata rows.",
                    }
                ],
            }
        if artifacts:
            return {"decision": {"action": "finalize"}}
        step = 5 - payload["remaining_steps"]
        return {
            "decision": {
                "action": "execute_python",
                "code": codes[step],
                "purpose": "Discover metadata then compute a registered count.",
            }
        }

    queue, claim, ctx, model, agent = await setup(
        b, response, python=executor, mode="deterministic"
    )
    result = await invoke(agent, claim, ctx, queue)
    assert result.result["result"]["status"] == "answered"
    assert result.result["artifact_refs"]
    assert len([r for r, _ in model.calls if r == "research"]) == 4
