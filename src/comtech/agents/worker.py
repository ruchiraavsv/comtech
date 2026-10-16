"""Private checkpointable exploration, finalization, and materialization subgraph."""

import json
import time
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from comtech.research import accounting
from comtech.research.ledger import BudgetExhausted

from .contracts import Decision, KnowledgeWorkerDraftResult
from .errors import InvalidModelOutput
from .evidence import materialize
from .model import MODEL_RETRY


class WorkerState(TypedDict, total=False):
    task: dict
    run_id: str
    cycle: int
    observations: dict
    history: list
    failures: list
    pending: dict | None
    exploration_closed: bool
    termination_reason: str
    deadline: float
    usage: dict
    draft: dict
    result: dict
    evidence: dict
    finalization_attempt: int
    finalization_error: str | None
    validation_issues: list[dict]


def emit(**fields):
    get_stream_writer()({"event": "agent.activity", **fields})


def build_worker(model, tools, counter, limits):
    def close(reason):
        return {"exploration_closed": True, "termination_reason": reason, "pending": None}

    def payload(state, final=False):
        data = {
            "task": state["task"],
            "observations": list(state["observations"].values()),
            "tool_history": state["history"],
            "failures": state["failures"],
            "cycle": state["cycle"],
        }
        if final:
            data["termination_reason"] = state["termination_reason"]
            data["validation_error"] = state.get("finalization_error")
            if state.get("finalization_error"):
                data["rejected_draft"] = state.get("draft")
                data["validation_issues"] = state.get("validation_issues", [])
                data["tool_history"] = []  # Keep room for the rejected draft and actual evidence.
        else:
            data["tools"] = tools.schemas
        return data

    def initialize(state):
        return {
            "cycle": 0,
            "observations": {},
            "history": [],
            "failures": [],
            "pending": None,
            "exploration_closed": False,
            "termination_reason": "completed",
            "deadline": time.time() + limits.worker_timeout_seconds,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "finalization_attempt": 0,
            "finalization_error": None,
        }

    async def decide(state):
        if state["exploration_closed"]:
            return {}
        if state["cycle"] >= limits.knowledge_worker_max_cycles:
            return close("cycle_limit")
        if time.time() >= state["deadline"]:
            return close("tool_failure")
        data = payload(state)
        size = model.input_size("decision", data, Decision)
        if size + limits.decision_output_tokens > limits.exploration_budget:
            return close("context_budget")
        try:
            decision, usage = await accounting.generate(
                model, "decision", data, Decision, limits.decision_output_tokens
            )
        except BudgetExhausted as error:
            return close(error.reason)
        except InvalidModelOutput as error:
            return {
                "cycle": state["cycle"] + 1,
                "pending": None,
                "failures": [
                    *state["failures"],
                    {
                        "tool_name": "decision",
                        "code": "INVALID_MODEL_OUTPUT",
                        "message": str(error),
                    },
                ],
            }
        selected = model.selection("decision", data)[0] if hasattr(model, "selection") else "test"
        emit(
            stage="worker_decision",
            model=selected,
            cycle=state["cycle"] + 1,
            context_tokens=size,
            **usage,
        )
        update = {
            "cycle": state["cycle"] + 1,
            "usage": {k: state["usage"][k] + usage[k] for k in usage},
        }
        if decision.action == "finalize":
            failed = state["failures"] and (
                decision.stop_due_to_tool_failure or not state["observations"]
            )
            return {**update, **close("tool_failure" if failed else "completed")}
        if decision.tool_name not in tools.schemas:
            raise ValueError("Model selected an unadvertised tool")
        # Reserve the entire serialized observation plus decision and message framing.
        needed = size + counter.count(decision) + tools.maximum(decision.tool_name) + 128
        if needed > limits.exploration_budget:
            return {**update, **close("context_budget")}
        return {**update, "pending": decision.model_dump()}

    async def execute(state):
        if state["pending"] is None:
            return {}  # Rejected model proposal consumed a cycle; no tool was selected.
        decision = Decision.model_validate(state["pending"])
        # Recheck on resume, before executing any external request.
        size = model.input_size("decision", payload(state), Decision)
        if size + counter.count(decision) + tools.maximum(decision.tool_name) + 128 > (
            limits.exploration_budget
        ):
            return close("context_budget")
        if time.time() >= state["deadline"]:
            return close("tool_failure")
        try:
            arguments = json.loads(decision.arguments_json)
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be an object")
        except (ValueError, TypeError):
            result = tools.failure(decision.tool_name, "INVALID_ARGUMENT", "Invalid JSON arguments")
        else:
            retry = any(
                h["error"]
                and h["decision"]["tool_name"] == decision.tool_name
                and h["decision"]["arguments_json"] == decision.arguments_json
                for h in state["history"]
            )
            try:
                result = await accounting.data_call(
                    decision.tool_name,
                    arguments,
                    lambda: tools.call(decision.tool_name, arguments),
                    retry=retry,
                    cycle=state["cycle"],
                )
            except BudgetExhausted as error:
                return close(error.reason)
        if counter.count(result) > tools.maximum(decision.tool_name):
            result = tools.failure(decision.tool_name, "RESULT_TOO_LARGE", "Result rejected")
        observations = dict(state["observations"])
        for item in result.observations:
            observations.setdefault(item.observation_id, item.model_dump(mode="json"))
        failures = list(state["failures"])
        if result.error:
            failures.append(result.error.model_dump())
        history = [
            *state["history"],
            {
                "decision": decision.model_dump(),
                "observation_ids": [o.observation_id for o in result.observations],
                "details": result.details,
                "section_options": getattr(result, "section_options", []),
                "section_options_truncated": getattr(result, "section_options_truncated", False),
                "omitted_sections": getattr(result, "omitted_sections", False),
                "error": result.error.model_dump() if result.error else None,
            },
        ]
        update = {
            "observations": observations,
            "history": history,
            "failures": failures,
            "pending": None,
        }
        next_state = {**state, **update}
        actual = model.input_size("decision", payload(next_state), Decision)
        if actual > limits.exploration_budget:
            # Preserve earlier bounded evidence, not an oversized newly observed response.
            return close("context_budget")
        emit(
            stage="worker_tool",
            tool=decision.tool_name,
            cycle=state["cycle"],
            context_tokens=actual,
            outcome=result.error.code if result.error else "OK",
        )
        if actual + limits.decision_output_tokens > limits.exploration_budget:
            update.update(close("context_budget"))
        elif state["cycle"] >= limits.knowledge_worker_max_cycles:
            update.update(close("cycle_limit"))
        return update

    async def finalize(state):
        data = payload(state, final=True)
        size = model.input_size("worker_finalize", data, KnowledgeWorkerDraftResult)
        available = min(limits.finalization_reserve, limits.total_context_budget - size)
        if available < 256:
            raise RuntimeError("Finalization reserve cannot fit prompt/schema")
        draft, usage = await accounting.generate(
            model, "worker_finalize", data, KnowledgeWorkerDraftResult, available
        )
        emit(
            stage="worker_finalized",
            cycle=state["cycle"],
            status=draft.status,
            termination_reason=state["termination_reason"],
            context_tokens=size,
            input_tokens=state["usage"]["input_tokens"] + usage["input_tokens"],
            output_tokens=state["usage"]["output_tokens"] + usage["output_tokens"],
        )
        return {
            "draft": draft.model_dump(),
            "finalization_attempt": state["finalization_attempt"] + 1,
            "usage": {k: state["usage"][k] + usage[k] for k in usage},
        }

    def materialize_node(state):
        from .contracts import Observation, ToolFailure

        try:
            result, evidence = materialize(
                KnowledgeWorkerDraftResult.model_validate(state["draft"]),
                {
                    key: Observation.model_validate(value)
                    for key, value in state["observations"].items()
                },
                state["run_id"],
                state["task"]["task_id"],
                state["termination_reason"],
                [ToolFailure.model_validate(f) for f in state["failures"]],
            )
        except ValueError as error:
            if state["finalization_attempt"] >= 2:
                raise
            # Structural feedback only. The LLM still owns every semantic claim.
            return Command(
                update={
                    "finalization_error": str(error),
                    "validation_issues": getattr(error, "issues", []),
                },
                goto="finalize",
            )
        return Command(
            update={
                "result": result.model_dump(),
                "evidence": {key: value.model_dump() for key, value in evidence.items()},
            },
            goto=END,
        )

    builder = StateGraph(WorkerState)
    builder.add_node("initialize", initialize)
    builder.add_node("decide", decide, retry_policy=MODEL_RETRY)
    builder.add_node("execute", execute)
    builder.add_node("finalize", finalize, retry_policy=MODEL_RETRY)
    builder.add_node("materialize", materialize_node)
    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "decide")
    builder.add_conditional_edges(
        "decide", lambda s: "finalize" if s["exploration_closed"] else "execute"
    )
    builder.add_conditional_edges(
        "execute", lambda s: "finalize" if s["exploration_closed"] else "decide"
    )
    builder.add_edge("finalize", "materialize")
    return builder.compile()
