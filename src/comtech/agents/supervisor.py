"""Version 2 adaptive Supervisor: model-selected tools, review, final rendering."""

from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Overwrite, Send

from comtech.research import accounting
from comtech.research.contracts import (
    DelegateAction,
    ResearchRequest,
    SpecialistResult,
    SupervisorTurn,
    parse_worker_result,
)
from comtech.research.ledger import AccountingError, BudgetExhausted

from .budget import serialized
from .contracts import FinalDraft, KnowledgeWorkerResult, ReviewDecision, SupervisorAnswerPackage
from .errors import ClaimValidationError, InvalidModelOutput
from .evidence import validate_package
from .graph import AppState, FinalInput, ReviewerInput, WorkerInput, build_legacy_graph, render
from .model import MODEL_RETRY
from .worker import build_worker, emit

GRAPH_VERSION = 2


def model_task_results(results):
    """Source text is already supplied once in the top-level evidence map."""
    return {
        key: {k: v for k, v in result.items() if k != "evidence"}
        if result.get("specialist") == "research"
        else result
        for key, result in results.items()
    }


class SupervisorState(AppState):
    graph_version: int
    objective_id: str | None
    supervisor_turns: int
    delegated_tasks: dict
    pending_calls: list[dict]
    exploration_closed: bool
    research_bindings: dict
    final_attempt: int
    final_error: str | None
    final_rejected_draft: dict | None
    package_validation_attempts: int
    citation_plan: dict
    final_fallback: bool


class ResearchReviewInput(ReviewerInput):
    research_bindings: dict
    messages: list
    citation_plan: dict


class ResearchFinalInput(FinalInput):
    research_bindings: dict
    task_results: dict
    final_attempt: int
    final_error: str | None
    final_rejected_draft: dict | None
    citation_plan: dict


class VersionedGraph:
    """Pending v1 runs finish on v1; subsequent user turns start on v2.

    Unknown versions fail closed. New input cannot overwrite a pending run.
    The adapter does not migrate checkpoints or replay completed worker tools.
    """

    def __init__(self, current, legacy, checkpointer):
        self.current, self.legacy, self.checkpointer = current, legacy, checkpointer

    async def _select(self, inputs, config):
        configured = (config or {}).get("configurable", {})
        context = accounting.CURRENT.get()
        if configured.get("objective_id") and context is None:
            raise AccountingError("Background graph requires trusted accounting context")
        if context:
            objective = await context.ledger.check(context.lease, "finalization")
            expected = {
                "app_run_id": objective["run_id"],
                "thread_id": objective["thread_id"],
                "objective_id": context.lease.objective_id,
            }
            if any(str(configured.get(k)) != str(v) for k, v in expected.items()):
                raise AccountingError("Graph configuration differs from accounting identity")
        if not self.checkpointer:
            return self.current
        snapshot = await self.current.aget_state(config)
        version = snapshot.values.get("graph_version", 1)
        if version not in (1, GRAPH_VERSION):
            raise ValueError(f"Unsupported checkpoint graph version: {version}")
        if snapshot.next:
            if context and version != GRAPH_VERSION:
                raise AccountingError("Background accounting cannot resume a legacy graph")
            if inputs is not None and not (context and isinstance(inputs, Command)):
                raise ValueError("Pending run must be resumed before starting another turn")
            return self.legacy if version == 1 else self.current
        if inputs is None:
            raise ValueError("No pending checkpoint to resume")
        return self.current

    async def ainvoke(self, inputs, config=None, **kwargs):
        graph = await self._select(inputs, config)
        return await graph.ainvoke(inputs, config, **kwargs)

    async def astream(self, inputs, config=None, **kwargs):
        graph = await self._select(inputs, config)
        async for item in graph.astream(inputs, config, **kwargs):
            yield item

    async def aget_state(self, config, **kwargs):
        return await self.current.aget_state(config, **kwargs)

    async def aget_state_history(self, config, **kwargs):
        async for item in self.current.aget_state_history(config, **kwargs):
            yield item


def build_supervisor_graph(model, tools, counter, limits, checkpointer=None, *, research=None):
    worker = build_worker(model, tools, counter, limits)
    # At most one delegation turn per task, plus one submission per review and
    # a small bounded allowance for malformed proposals. Retries are separate.
    max_turns = limits.max_tasks + limits.max_review_cycles + 2

    async def call(role, payload, schema, *, final=False):
        size = model.input_size(role, payload, schema)
        available = min(4000, model.context_window - size)
        if available < 512:
            raise RuntimeError("Role context exceeded; no unbounded prompt expansion")
        value, usage = await accounting.generate(
            model, role, payload, schema, available, final=final
        )
        selected = model.selection(role, payload)[0] if hasattr(model, "selection") else "test"
        emit(stage=role, model=selected, context_tokens=size, **usage)
        return value

    def begin(state, config):
        return {
            "graph_version": GRAPH_VERSION,
            "objective_id": config.get("configurable", {}).get("objective_id"),
            "run_id": config.get("configurable", {}).get("app_run_id") or str(uuid4()),
            "supervisor_turns": 0,
            "delegated_tasks": {},
            "pending_calls": [],
            "exploration_closed": False,
            "research_bindings": {},
            "task_results": Overwrite({}),
            "evidence": Overwrite({}),
            "review_cycle": 0,
            "plan": {},
            "answer_package": {},
            "review_decision": {},
            "validation_errors": [],
            "final_answer": "",
            "resolved_request": "",
            "final_attempt": 0,
            "final_error": None,
            "final_rejected_draft": None,
            "citation_plan": {},
            "final_fallback": False,
            "package_validation_attempts": 0,
        }

    async def supervisor(state):
        turn = state["supervisor_turns"] + 1
        if turn > max_turns:
            raise RuntimeError("Supervisor turn limit reached; no approved answer is available")
        remaining = limits.max_tasks - len(state["delegated_tasks"])
        payload = {
            "prompt_version": "supervisor-v2",
            "conversation": [{"role": m.type, "content": m.content} for m in state["messages"]],
            "resolved_request": state["resolved_request"],
            "task_results": model_task_results(state["task_results"]),
            "evidence": state["evidence"],
            "available_research_input_refs": sorted(
                {
                    ref
                    for result in state["task_results"].values()
                    if result.get("specialist") == "research"
                    for ref in [
                        *result.get("evidence", {}),
                        *result.get("artifact_refs", []),
                        *(
                            c["computation_ref"]
                            for c in result["result"]["claims"]
                            if c.get("computation_ref")
                        ),
                    ]
                }
            ),
            "delegated_tasks": state["delegated_tasks"],
            "review": state["review_decision"],
            "validation_errors": state["validation_errors"],
            "remaining_tasks": remaining,
            "remaining_turns": max_turns - turn,
            "available_specialists": [
                "knowledge_worker",
                *(["research"] if research and accounting.CURRENT.get() else []),
            ]
            if remaining and not state.get("exploration_closed")
            else [],
        }
        closed = state.get("exploration_closed", False)
        if state.get("package_validation_attempts"):
            payload["rejected_answer_package"] = state["answer_package"]
        try:
            try:
                value = await call("supervisor", payload, SupervisorTurn, final=closed)
            except BudgetExhausted as error:
                closed = True
                payload.update(
                    available_specialists=[],
                    remaining_tasks=0,
                    exploration_closed=True,
                    termination_reason=error.reason,
                )
                value = await call("supervisor", payload, SupervisorTurn, final=True)
        except InvalidModelOutput as error:
            return Command(
                update={
                    "supervisor_turns": turn,
                    "validation_errors": [str(error)],
                    "exploration_closed": closed,
                },
                goto="supervisor",
            )
        decision = value.decision
        update = {"supervisor_turns": turn, "validation_errors": [], "exploration_closed": closed}
        if isinstance(decision, DelegateAction):
            try:
                if closed:
                    raise ValueError("Exploration is closed; submit from existing evidence")
                if len(decision.calls) > remaining:
                    raise ValueError("Delegation exceeds remaining task capacity")
                ids = [c.task.task_id for c in decision.calls]
                if len(set(ids)) != len(ids) or set(ids).intersection(state["delegated_tasks"]):
                    raise ValueError("Delegation task IDs must be new and unique")
                for item in decision.calls:
                    if item.specialist == "research" and research is None:
                        raise ValueError("Specialist is unavailable")
                    if item.specialist == "knowledge_worker" and not set(
                        item.task.depends_on
                    ).issubset(state["task_results"]):
                        raise ValueError(
                            "Inspect completed dependencies before proposing follow-up work"
                        )
            except ValueError as error:
                return Command(
                    update={**update, "validation_errors": [str(error)]}, goto="supervisor"
                )
            calls = [item.model_dump() for item in decision.calls]
            update.update(
                resolved_request=decision.resolved_request,
                pending_calls=calls,
                delegated_tasks={
                    **state["delegated_tasks"],
                    **{c["task"]["task_id"]: c for c in calls},
                },
            )
            return Command(update=update, goto="execute_tools")
        update["answer_package"] = decision.answer.model_dump()
        update["resolved_request"] = decision.answer.resolved_request
        return Command(update=update, goto="validate")

    async def execute_tools(state):
        remaining = [
            c for c in state["pending_calls"] if c["task"]["task_id"] not in state["task_results"]
        ]
        if not remaining:
            return Command(update={"pending_calls": []}, goto="supervisor")
        sends = []
        for item in remaining[: limits.parallel_workers]:
            if item["specialist"] == "research":
                if sends:
                    break
                try:
                    root = await research.admit(ResearchRequest.model_validate(item["task"]))
                except BudgetExhausted:
                    return Command(
                        update={
                            "pending_calls": [],
                            "exploration_closed": True,
                            "validation_errors": ["Shared budget prevented Research admission."],
                        },
                        goto="supervisor",
                    )
                except ValueError as error:
                    # Admission is transactional. Rejected/pending proposals have not run;
                    # retain completed work and let the next bounded turn correct the batch.
                    abandoned = {c["task"]["task_id"] for c in remaining}
                    return Command(
                        update={
                            "pending_calls": [],
                            "delegated_tasks": {
                                k: v
                                for k, v in state["delegated_tasks"].items()
                                if k not in abandoned
                            },
                            "validation_errors": [
                                f"Research admission rejected task {item['task']['task_id']}: "
                                + str(error)[:1000]
                            ],
                        },
                        goto="supervisor",
                    )
                return Command(
                    update={
                        "research_bindings": {
                            **state["research_bindings"],
                            item["task"]["task_id"]: root,
                        }
                    },
                    goto="research",
                )
            try:
                await accounting.admit_worker(item["task"]["task_id"], limits)
            except BudgetExhausted:
                if sends:
                    break  # First admitted worker may free capacity for the next.
                return Command(
                    update={
                        "pending_calls": [],
                        "exploration_closed": True,
                        "validation_errors": [
                            "Shared budget prevented remaining work; finalize supported findings."
                        ],
                    },
                    goto="supervisor",
                )
            task = dict(item["task"])
            if task["depends_on"]:
                task["context"] += "\nDependency results:\n" + serialized(
                    {k: state["task_results"][k] for k in task["depends_on"]}
                )
            sends.append(Send("knowledge_worker", {"task": task, "run_id": state["run_id"]}))
        return Command(goto=sends)

    async def run_worker(state: WorkerInput):
        with accounting.worker_scope(state["task"]["task_id"]) as context:
            try:
                output = await worker.ainvoke(state)
            except ClaimValidationError as error:
                # A failed local draft cannot invalidate independent completed tasks.
                result = KnowledgeWorkerResult(
                    task_id=state["task"]["task_id"],
                    status="partial",
                    termination_reason="completed",
                    claims=[],
                    source_conflicts=[],
                    clarification=None,
                    unresolved=[
                        {
                            "information_need": state["task"]["objective"],
                            "reason": "insufficient_evidence",
                            "attempted_sources": [],
                            "details": "Worker draft failed attribution validation after "
                            "correction; no findings from this task are validated.",
                        }
                    ],
                    tool_failures=[
                        {
                            "tool_name": "worker_finalize",
                            "code": "INVALID_CLAIMS",
                            "message": str(error)[:1000],
                        }
                    ],
                )
                output = {"result": result.model_dump(mode="json"), "evidence": {}}
            finally:
                if context:
                    await context.ledger.release_hold(context.lease, context.scope)
        return {
            "task_results": {state["task"]["task_id"]: output["result"]},
            "evidence": output["evidence"],
        }

    async def run_research(state):
        _, envelopes = await research.collect(state["research_bindings"])
        return {
            "task_results": {k: v.model_dump(mode="json") for k, v in envelopes.items()},
            "evidence": {
                k: v.model_dump(mode="json")
                for e in envelopes.values()
                for k, v in e.evidence.items()
            },
        }

    async def registry_for(state):
        if state.get("research_bindings"):
            return await research.validate(state["research_bindings"], state["task_results"])
        return None

    async def validate(state):
        try:
            registry = await registry_for(state)
            citation_plan = validate_package(
                SupervisorAnswerPackage.model_validate(state["answer_package"]),
                {
                    k: SpecialistResult.model_validate(v)
                    if v.get("specialist") == "research"
                    else parse_worker_result(v)
                    for k, v in state["task_results"].items()
                },
                state["evidence"],
                registry,
            )
        except ClaimValidationError as error:
            if state.get("package_validation_attempts", 0) >= 1:
                raise RuntimeError(
                    "Answer package validation failed after correction: " + str(error)
                ) from error
            return Command(
                update={"validation_errors": [str(error)], "package_validation_attempts": 1},
                goto="supervisor",
            )
        except ValueError as error:
            raise RuntimeError("Trusted evidence validation failed: " + str(error)) from error
        return Command(
            update={
                "validation_errors": [],
                "package_validation_attempts": 0,
                "citation_plan": citation_plan,
            },
            goto="reviewer",
        )

    async def review(state: ResearchReviewInput):
        payload = dict(state)
        payload["task_results"] = model_task_results(state["task_results"])
        messages = payload.pop("messages", [])
        payload["user_request"] = next(
            (m.content for m in reversed(messages) if m.type == "human"), ""
        )
        registry = await registry_for(state)
        if registry:
            payload["computations"] = registry.review_computations(counter)
        payload["validated_premise_ids"] = sorted(
            {
                c["claim_id"]
                for result in payload["task_results"].values()
                for c in result.get("result", result).get("claims", [])
            }
        )
        value = await call("review", payload, ReviewDecision)
        cycle = state["review_cycle"] + 1
        approved = (
            value.status == "approved"
            and not state["validation_errors"]
            and not any(i.severity == "blocking" for i in value.issues)
        )
        if not approved:
            value = value.model_copy(
                update={
                    "status": "revise_supervisor",
                    "required_changes": [*value.required_changes, *state["validation_errors"]],
                }
            )
        return Command(
            update={"review_decision": value.model_dump(), "review_cycle": cycle},
            goto="final_answer"
            if approved
            else ("review_failed" if cycle >= min(2, limits.max_review_cycles) else "supervisor"),
        )

    def failed(state):
        raise RuntimeError("Review limit reached; no approved answer is available")

    async def final(state: ResearchFinalInput):
        package = SupervisorAnswerPackage.model_validate(state["answer_package"])
        # Final wording consumes approved claims; render() attaches verified citations.
        payload = {k: state[k] for k in ("resolved_request", "answer_package")}
        attempt = state.get("final_attempt", 0) + 1
        payload.update(final_attempt=attempt, validation_error=state.get("final_error"))
        if state.get("final_error"):
            payload["rejected_draft"] = state.get("final_rejected_draft")
        registry = await registry_for(state)
        # Recheck trusted records outside the wording retry: the writer cannot repair
        # changed evidence or authorization. Both stages use the same resolver.
        citation_plan = validate_package(
            package,
            {
                k: SpecialistResult.model_validate(v)
                if v.get("specialist") == "research"
                else parse_worker_result(v)
                for k, v in state["task_results"].items()
            },
            state["evidence"],
            registry,
        )
        draft = None
        fallback = False
        try:
            draft = await call("final", payload, FinalDraft)
            answer = render(draft, package, state["evidence"], registry, citation_plan)
        except ValueError as error:
            if attempt >= 2:
                # Only already-approved statements are eligible for this fallback.
                draft = FinalDraft(
                    paragraphs=[
                        {"text": c.statement, "claim_ids": [c.claim_id]} for c in package.claims
                    ]
                )
                answer = render(draft, package, state["evidence"], registry, citation_plan)
                fallback = True
            else:
                return Command(
                    update={
                        "final_attempt": attempt,
                        "final_error": str(error)[:1000],
                        "final_rejected_draft": draft.model_dump(mode="json") if draft else None,
                    },
                    goto="final_answer",
                )
        return Command(
            update={
                "final_attempt": attempt,
                "final_error": None,
                "final_rejected_draft": None,
                "final_answer": answer,
                "final_fallback": fallback,
                "messages": [AIMessage(content=answer)],
            },
            goto=END,
        )

    builder = StateGraph(SupervisorState)
    builder.add_node("begin", begin)
    builder.add_node("supervisor", supervisor, retry_policy=MODEL_RETRY)
    builder.add_node("execute_tools", execute_tools)
    builder.add_node("knowledge_worker", run_worker, input_schema=WorkerInput)
    builder.add_node("research", run_research)
    builder.add_node("validate", validate)
    builder.add_node("reviewer", review, input_schema=ResearchReviewInput, retry_policy=MODEL_RETRY)
    builder.add_node("review_failed", failed)
    builder.add_node(
        "final_answer", final, input_schema=ResearchFinalInput, retry_policy=MODEL_RETRY
    )
    builder.add_edge(START, "begin")
    builder.add_edge("begin", "supervisor")
    builder.add_edge("knowledge_worker", "execute_tools")
    builder.add_edge("research", "execute_tools")
    builder.add_edge("review_failed", END)
    return VersionedGraph(
        builder.compile(checkpointer=checkpointer),
        build_legacy_graph(model, tools, counter, limits, checkpointer),
        checkpointer,
    )
