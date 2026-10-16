"""Supervisor, worker fan-out, review gate and approved answer rendering."""

import re
from operator import or_
from typing import Annotated, TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, Overwrite, Send

from .contracts import (
    EvidenceRecord,
    FinalDraft,
    KnowledgeTask,
    KnowledgeWorkerResult,
    ReviewDecision,
    SupervisorAnswerPackage,
    SupervisorPlan,
)
from .evidence import validate_package
from .model import MODEL_RETRY
from .worker import build_worker, emit


class AppState(MessagesState):
    run_id: str
    resolved_request: str
    plan: dict
    task_results: Annotated[dict, or_]
    evidence: Annotated[dict, or_]
    answer_package: dict
    review_decision: dict
    review_cycle: int
    validation_errors: list[str]
    final_answer: str


class WorkerInput(TypedDict):
    task: dict
    run_id: str


class ReviewerInput(TypedDict):
    resolved_request: str
    answer_package: dict
    task_results: dict
    evidence: dict
    review_cycle: int
    validation_errors: list[str]


class FinalInput(TypedDict):
    resolved_request: str
    answer_package: dict
    evidence: dict


def check_plan(tasks, maximum, completed=()):
    if len(tasks) > maximum or len({t.task_id for t in tasks}) != len(tasks):
        raise ValueError("Task count or identity limit exceeded")
    indexed = {t.task_id: t for t in tasks}
    seen, active = set(completed), set()

    def visit(key):
        if key in active:
            raise ValueError("Cyclic task dependencies")
        if key in seen:
            return
        if key not in indexed:
            raise ValueError("Unknown task dependency")
        active.add(key)
        for dep in indexed[key].depends_on:
            visit(dep)
        active.remove(key)
        seen.add(key)

    for key in indexed:
        visit(key)


def render(draft, package, evidence, registry=None, citation_plan=None):
    from .citations import resolve_citations, source_description, source_key

    claims = {c.claim_id: c for c in package.claims}
    plan = (
        citation_plan
        if citation_plan is not None
        else resolve_citations(package, evidence, registry)
    )
    used, paragraphs, cited = set(), [], {}
    source_groups = {}
    for index, paragraph in enumerate(draft.paragraphs):
        if (
            not paragraph.text.strip()
            or not paragraph.claim_ids
            or not set(paragraph.claim_ids).issubset(claims)
        ):
            raise ValueError(
                f"Final output lacks approved claim attribution at paragraphs[{index}].claim_ids: "
                f"{paragraph.claim_ids}. Allowed claim IDs: {list(claims)}"
            )
        if re.search(r"(?<!\w)EV-", paragraph.text) or "](http" in paragraph.text:
            raise ValueError("Final model must not invent citation markup")
        used.update(paragraph.claim_ids)
        ids = sorted(
            {c["ref"] for key in paragraph.claim_ids for c in plan[key] if c["kind"] == "source"}
        )
        labels = []
        for eid in ids:
            if eid not in evidence:
                raise ValueError("Unresolved citation")
            record = EvidenceRecord.model_validate(evidence[eid])
            group = source_key(record)
            source_groups.setdefault(group, {})[eid] = record
            cited.setdefault(group, len(cited) + 1)
            labels.append(f"[{cited[group]}]")
        for key in paragraph.claim_ids:
            for citation in plan[key]:
                if citation["kind"] == "source":
                    continue
                ref = (citation["ref"], citation["description"])
                cited.setdefault(ref, len(cited) + 1)
                labels.append(f"[{cited[ref]}]")
        paragraphs.append(paragraph.text.strip() + " " + " ".join(dict.fromkeys(labels)))
    if used != set(claims):
        raise ValueError("Final output omits approved claims")
    paragraphs.extend(package.limitations)
    paragraphs.extend(f"Unresolved: {u.information_need} — {u.details}" for u in package.unresolved)
    paragraphs.extend(f"Source conflict: {c.description}" for c in package.source_conflicts)
    if package.clarification:
        paragraphs.append(package.clarification.question)
    if not paragraphs:
        raise ValueError("Empty final answer package")
    for eid, number in cited.items():
        if eid not in source_groups:
            paragraphs.append(f"[{number}] {eid[1]}")
            continue
        paragraphs.append(f"[{number}] {source_description(list(source_groups[eid].values()))}")
    return "\n\n".join(paragraphs)


def build_legacy_graph(model, tools, counter, limits, checkpointer=None):
    """Version 1 topology, retained solely for already-pending checkpoints."""
    worker = build_worker(model, tools, counter, limits)

    async def call(role, payload, schema):
        size = model.input_size(role, payload, schema)
        available = min(4000, model.context_window - size)
        if available < 512:
            raise RuntimeError("Role context exceeded; no unbounded prompt expansion")
        value, usage = await model.generate(role, payload, schema, available)
        selected = model.selection(role, payload)[0] if hasattr(model, "selection") else "test"
        emit(stage=role, model=selected, context_tokens=size, **usage)
        return value

    def begin(state):
        return {
            "run_id": str(uuid4()),
            "task_results": Overwrite({}),
            "evidence": Overwrite({}),
            "review_cycle": 0,
            "plan": {},
            "answer_package": {},
            "review_decision": {},
            "validation_errors": [],
            "final_answer": "",
            "resolved_request": "",
        }

    async def plan(state):
        history = [{"role": m.type, "content": m.content} for m in state["messages"]]
        value = await call(
            "plan", {"conversation": history, "max_tasks": limits.max_tasks}, SupervisorPlan
        )
        check_plan(value.tasks, limits.max_tasks)
        return {"plan": value.model_dump(), "resolved_request": value.resolved_request}

    def dispatch(state):
        tasks = [KnowledgeTask.model_validate(t) for t in state["plan"]["tasks"]]
        remaining = [t for t in tasks if t.task_id not in state["task_results"]]
        if not remaining:
            return Command(goto="supervisor_synthesize")
        ready = [t for t in remaining if set(t.depends_on).issubset(state["task_results"])]
        if not ready:
            raise ValueError("Task dependency deadlock")
        sends = []
        for task in ready[: limits.parallel_workers]:
            if task.depends_on:
                from .budget import serialized

                task = task.model_copy(
                    update={
                        "context": task.context
                        + "\nDependency results:\n"
                        + serialized({k: state["task_results"][k] for k in task.depends_on})
                    }
                )
            sends.append(
                Send("knowledge_worker", {"task": task.model_dump(), "run_id": state["run_id"]})
            )
        return Command(goto=sends)

    async def run_worker(state: WorkerInput):
        output = await worker.ainvoke(state)
        return {
            "task_results": {state["task"]["task_id"]: output["result"]},
            "evidence": output["evidence"],
        }

    async def synthesize(state):
        value = await call(
            "synthesize",
            {
                "resolved_request": state["resolved_request"],
                "task_results": state["task_results"],
                "evidence": state["evidence"],
                "review": state["review_decision"],
            },
            SupervisorAnswerPackage,
        )
        return {"answer_package": value.model_dump()}

    def validate(state):
        try:
            validate_package(
                SupervisorAnswerPackage.model_validate(state["answer_package"]),
                {
                    k: KnowledgeWorkerResult.model_validate(v)
                    for k, v in state["task_results"].items()
                },
                state["evidence"],
            )
        except ValueError as error:
            return {"validation_errors": [str(error)]}
        return {"validation_errors": []}

    async def review(state: ReviewerInput):
        value = await call("review", state, ReviewDecision)
        cycle = state["review_cycle"] + 1
        approved = (
            value.status == "approved"
            and not state["validation_errors"]
            and not any(issue.severity == "blocking" for issue in value.issues)
        )
        if approved:
            return Command(
                update={"review_decision": value.model_dump(), "review_cycle": cycle},
                goto="final_answer",
            )
        value = value.model_copy(
            update={
                "status": "revise_supervisor",
                "required_changes": [*value.required_changes, *state["validation_errors"]],
            }
        )
        return Command(
            update={"review_decision": value.model_dump(), "review_cycle": cycle},
            goto="review_failed" if cycle >= limits.max_review_cycles else "repair",
        )

    async def repair(state):
        review = ReviewDecision.model_validate(state["review_decision"])
        if not review.followup_tasks:
            return Command(goto="supervisor_synthesize")
        previous = [KnowledgeTask.model_validate(t) for t in state["plan"]["tasks"]]
        new = await call(
            "plan",
            {
                "resolved_request": state["resolved_request"],
                "existing_tasks": previous,
                "task_results": state["task_results"],
                "review": review,
                "max_tasks": limits.max_tasks - len(previous),
                "instruction": "Plan only necessary follow-up objectives with new IDs; "
                "can be empty.",
            },
            SupervisorPlan,
        )
        combined = [*previous, *new.tasks]
        check_plan(combined, limits.max_tasks)
        return Command(
            update={
                "plan": {
                    "resolved_request": state["resolved_request"],
                    "tasks": [t.model_dump() for t in combined],
                }
            },
            goto="dispatch",
        )

    def failed(state):
        raise RuntimeError("Review limit reached; no approved answer is available")

    async def final(state: FinalInput):
        package = SupervisorAnswerPackage.model_validate(state["answer_package"])
        draft = await call("final", state, FinalDraft)
        answer = render(draft, package, state["evidence"])
        return {"final_answer": answer, "messages": [AIMessage(content=answer)]}

    builder = StateGraph(AppState)
    for name, node in [
        ("begin", begin),
        ("supervisor_plan", plan),
        ("dispatch", dispatch),
        ("supervisor_synthesize", synthesize),
        ("validate", validate),
        ("repair", repair),
        ("review_failed", failed),
    ]:
        builder.add_node(
            name,
            node,
            retry_policy=MODEL_RETRY
            if name in ("supervisor_plan", "supervisor_synthesize", "repair")
            else None,
        )
    builder.add_node("knowledge_worker", run_worker, input_schema=WorkerInput)
    builder.add_node("reviewer", review, input_schema=ReviewerInput, retry_policy=MODEL_RETRY)
    builder.add_node("final_answer", final, input_schema=FinalInput, retry_policy=MODEL_RETRY)
    builder.add_edge(START, "begin")
    builder.add_edge("begin", "supervisor_plan")
    builder.add_edge("supervisor_plan", "dispatch")
    builder.add_edge("knowledge_worker", "dispatch")
    builder.add_edge("supervisor_synthesize", "validate")
    builder.add_edge("validate", "reviewer")
    builder.add_edge("final_answer", END)
    builder.add_edge("review_failed", END)
    return builder.compile(checkpointer=checkpointer)


def build_enterprise_graph(model, tools, counter, limits, checkpointer=None):
    from .supervisor import build_supervisor_graph

    return build_supervisor_graph(model, tools, counter, limits, checkpointer)
