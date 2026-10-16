"""Checkpointed Research handler for the existing fenced background scheduler."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from comtech.agents.contracts import ToolFailure
from comtech.agents.errors import ClaimValidationError, InvalidModelOutput
from comtech.retrieval.tools import document_schemas

from . import accounting
from .access import Access
from .actions import PROMPT_VERSION, ResearchDraft, ResearchLimits, ResearchTurn
from .admission import Admission
from .broker import REQUESTS
from .broker_contracts import SDK_RESULT_GUIDE, BrokerError
from .contracts import SourceScope, SpecialistResult
from .ledger import BudgetExhausted
from .result_registry import ResultRegistry
from .scheduler import Outcome


class ResearchState(TypedDict, total=False):
    task_id: str
    objective_id: str
    input: dict
    user_request: str
    refs: list[str]
    children: list[str]
    joined: list[dict]
    steps: int
    stalls: int
    fingerprints: list[str]
    failures: list[dict]
    last_result: dict
    action: dict
    decision_model: str
    reason: str
    result: dict
    waiting: bool
    finalization_attempt: int
    rejected_draft: dict
    validation_issues: list[dict]


class ResearchAgent:
    def __init__(self, model, broker, python, queue, checkpointer, limits=None):
        if checkpointer is None:
            raise ValueError("Research requires a durable checkpointer")
        self.model, self.broker, self.python, self.queue = model, broker, python, queue
        self.limits = limits or ResearchLimits()
        self.admission = Admission(queue, self.limits)
        self.registry = ResultRegistry(broker)
        self.counter = broker.counter
        graph = StateGraph(ResearchState)
        graph.add_node("join", self.join)
        graph.add_node("decide", self.decide)
        graph.add_node("act", self.act)
        graph.add_node("finalize", self.finalize)
        graph.add_edge(START, "join")
        graph.add_edge("join", "decide")
        self.graph = graph.compile(checkpointer=checkpointer)

    def access(self, state):
        context = accounting.CURRENT.get()
        if (
            context is None
            or str(context.lease.task_id) != state["task_id"]
            or str(context.lease.objective_id) != state["objective_id"]
        ):
            raise ValueError("Research state differs from trusted task identity")
        return Access(
            context, SourceScope.model_validate(state["input"]["narrowed_scope"]), None, ""
        )

    async def __call__(self, claim):
        if claim.task["input"].get("prompt_version") != PROMPT_VERSION:
            raise ValueError("Unsupported Research prompt/checkpoint version")
        config = {
            "configurable": {"thread_id": "research:" + str(claim.task["id"])},
            "recursion_limit": 100,
        }
        snapshot = await self.graph.aget_state(config)
        if snapshot.values:
            self.access(snapshot.values)
            if snapshot.values.get("result"):
                return Outcome(result=snapshot.values["result"])
            inputs = None if snapshot.next else {"joined": claim.dependencies, "waiting": False}
        else:
            async with self.queue.pool.connection() as conn:
                run = await (
                    await conn.execute(
                        "SELECT input->>'message' AS message FROM app_runs WHERE id=%s",
                        (claim.objective["run_id"],),
                    )
                ).fetchone()
            inputs = {
                "task_id": str(claim.task["id"]),
                "objective_id": str(claim.objective["id"]),
                "input": claim.task["input"],
                "user_request": run["message"] or "" if run else "",
                "refs": claim.task["input"]["input_refs"],
                "children": [],
                "joined": claim.dependencies,
                "steps": 0,
                "stalls": 0,
                "fingerprints": [],
                "failures": [],
                "last_result": {},
                "reason": "",
                "waiting": False,
            }
        state = await self.graph.ainvoke(inputs, config, durability="sync")
        if state.get("result"):
            return Outcome(result=state["result"])
        if state["waiting"]:
            return Outcome(
                state="waiting_children",
                dependencies=tuple(state["children"]),
                continuation={"research_thread": config["configurable"]["thread_id"]},
            )
        raise ValueError("Research stopped without a result or dependencies")

    async def join(self, state):
        access = self.access(state)
        await access.context.ledger.check(access.context.lease, "finalization")
        refs, fresh, failures = set(state["refs"]), False, list(state["failures"])
        for child in state.get("joined", []):
            if str(child["id"]) not in state["children"]:
                raise ValueError("Undeclared child delivery")
            if child["state"] == "completed" and child["result"]:
                result = SpecialistResult.model_validate(child["result"])
                selected = set(result.evidence) | set(result.artifact_refs)
                selected.update(
                    c.computation_ref for c in result.result.claims if c.computation_ref
                )
                for ref in selected:
                    await self.broker.records.grant(
                        access.context.lease, ref, access.context.lease.task_id
                    )
                fresh |= bool(selected - refs)
                refs.update(selected)
            elif child["state"] in ("failed", "cancelled"):
                failure = ToolFailure(
                    tool_name="delegate",
                    code=child["state"],
                    message=f"Child {child['id']}: {child['termination_reason']}",
                ).model_dump()
                if failure not in failures:
                    failures.append(failure)
        return {
            "refs": sorted(refs),
            "stalls": 0 if fresh else state["stalls"],
            "failures": failures,
            "joined": [],
        }

    async def payload(self, state):
        access = self.access(state)
        registry = await self.registry.load(access, state["refs"], state["children"])
        evidence = {k: v.model_dump(mode="json") for k, v in registry.evidence.items()}
        artifacts = {}
        for key, value in (registry.artifacts | registry.queries).items():
            if key in registry.document_handles:
                continue
            if (
                key in registry.queries
                and registry.coverage[value.coverage_ref].method == "targeted"
            ):
                continue  # Direct retrieval is already represented by exact evidence spans.
            artifacts[key] = {
                "manifest": value.model_dump(mode="json"),
                "coverage": registry.coverage[value.coverage_ref].model_dump(mode="json"),
            }
            # Large tables remain referenced; a calculation must return a compact supported summary.
            raw = registry.payloads[value.result_ref]
            artifacts[key]["result"] = raw if self.counter.count(raw) <= 3000 else None
            artifacts[key]["result_omitted"] = artifacts[key]["result"] is None
        payload = {
            "prompt_version": PROMPT_VERSION,
            "task": state["input"],
            "user_request": state.get("user_request", ""),
            "evidence": evidence,
            "artifacts": artifacts,
            "child_claims": {
                k: v.claim.model_dump(mode="json") for k, v in registry.claims.items()
            },
            "failures": state["failures"],
            "last_result": state["last_result"],
            "termination_reason": state["reason"],
            "remaining_steps": self.limits.max_steps - state["steps"],
        }
        return payload, registry

    async def decide(self, state):
        if state["reason"]:
            return Command(goto="finalize")
        if state["steps"] >= self.limits.max_steps or state["stalls"] >= 2:
            return Command(
                update={"reason": "no_progress" if state["stalls"] >= 2 else "cycle_limit"},
                goto="finalize",
            )
        payload, _ = await self.payload(state)
        scope = self.access(state).scope
        payload["tools"] = {
            k: v for k, v in document_schemas(self.broker.limits).items() if k in scope.capabilities
        }
        payload["python_available"] = self.python is not None
        if self.python is not None:
            payload["sdk_schemas"] = {
                k: payload["tools"][k]["parameters"]
                if k in payload["tools"]
                else v.model_json_schema()
                for k, v in REQUESTS.items()
                if k in scope.capabilities
            }
            payload["sdk_results"] = {
                k: v for k, v in SDK_RESULT_GUIDE.items() if k in scope.capabilities
            }
            if "enumerate_documents" in payload["sdk_schemas"]:
                policy = payload["sdk_schemas"]["enumerate_documents"]["properties"][
                    "version_policy"
                ]
                policy.update(
                    enum=[scope.document_version_policy], default=scope.document_version_policy
                )
        maximum = 2000
        size = self.model.input_size("research", payload, ResearchTurn)
        ceiling = min(self.limits.context_tokens, self.model.context_window)
        # Leave output reserve and room for the largest bounded expansion before dispatch.
        if size + maximum + 3000 > ceiling - self.limits.final_output_tokens:
            return Command(update={"reason": "context_budget"}, goto="finalize")
        try:
            selected_model = (
                self.model.selection("research", payload)[0]
                if hasattr(self.model, "selection")
                else type(self.model).__name__
            )
            decision, _ = await accounting.generate(
                self.model, "research", payload, ResearchTurn, maximum
            )
        except BudgetExhausted as error:
            return Command(update={"reason": error.reason}, goto="finalize")
        except InvalidModelOutput as error:
            return Command(
                update={
                    "steps": state["steps"] + 1,
                    "stalls": state["stalls"] + 1,
                    "failures": [
                        *state["failures"],
                        ToolFailure(
                            tool_name="decision", code="INVALID_MODEL_OUTPUT", message=str(error)
                        ).model_dump(),
                    ],
                },
                goto="decide",
            )
        action = decision.decision.model_dump(mode="json")
        return Command(
            update={
                "action": action,
                "decision_model": selected_model,
                "steps": state["steps"] + 1,
                "reason": "completed" if action["action"] == "finalize" else "",
            },
            goto="finalize" if action["action"] == "finalize" else "act",
        )

    async def act(self, state):
        access = self.access(state)
        action = ResearchTurn(decision=state["action"]).decision
        key = f"research-v1:{state['steps']}"
        refs, failures, result = set(state["refs"]), list(state["failures"]), {}
        try:
            await access.context.ledger.check(access.context.lease)
            # Recheck actual tool input against the local ceiling before any execution.
            if self.counter.count(action) > 3000:
                return Command(update={"reason": "context_budget"}, goto="finalize")
            if action.action == "delegate":
                try:
                    children = await self.admission.propose(access.context.lease, action.children)
                except BudgetExhausted as error:
                    if error.reason != "objective_budget":
                        raise
                    # Atomic admission rolled back; a smaller batch or direct lookup may
                    # still fit. The next decision is charged normally and all caps remain.
                    failure = ToolFailure(
                        tool_name="delegate",
                        code="BUDGET_NOT_ADMITTED",
                        message=f"Child batch was not admitted ({error.reason}). Try fewer "
                        "children or a targeted direct read if needed; otherwise finalize "
                        "from existing evidence. No child in this batch was created.",
                    ).model_dump()
                    return Command(
                        update={"failures": [*failures, failure], "stalls": state["stalls"] + 1},
                        goto="decide",
                    )
                return Command(
                    update={
                        "children": sorted(set(state["children"]) | set(map(str, children))),
                        "waiting": True,
                        "stalls": state["stalls"] + 1,
                    },
                    goto=END,
                )
            if action.action == "execute_python":
                if self.python is None:
                    raise BrokerError("CAPABILITY_UNAVAILABLE", "Python runner is unavailable")
                result = await self.python.execute(
                    access.context,
                    action.code,
                    action.purpose,
                    action.input_refs,
                    request_id=key,
                    analysis_provenance={
                        "prompt_version": PROMPT_VERSION,
                        "model": state["decision_model"],
                        "decision_step": str(state["steps"]),
                        "analysis_mode": state["input"]["analysis_mode"],
                    },
                )
                # Executor exports only successful source receipts on a failed execution;
                # artifacts from an unsuccessful computation are never admitted here.
                refs.update(result.get("receipt_refs", []))
                failures.extend(result.get("data_errors", []))
                if result["status"] != "success":
                    failures.append(
                        ToolFailure(
                            tool_name=action.action,
                            code=result["status"],
                            message=result.get("error", "Execution failed"),
                        ).model_dump()
                    )
            else:
                token = await self.broker.capabilities.issue(access.context.lease)
                try:
                    reply = await self.broker.call(
                        token,
                        action.action,
                        action.arguments.model_dump(mode="json"),
                        request_id=key,
                    )
                finally:
                    await self.broker.capabilities.revoke(token)
                result = reply["value"]
                if reply["receipt_ref"]:
                    refs.add(reply["receipt_ref"])
                if result.get("error"):
                    failures.append(result["error"])
                result = {
                    "tool": action.action,
                    "receipt_ref": reply["receipt_ref"],
                    "details": result.get("details", ""),
                    "error": result.get("error"),
                    "section_options": result.get("section_options", []),
                    "section_options_truncated": result.get("section_options_truncated", False),
                    "omitted_sections": result.get("omitted_sections", False),
                }
        except BudgetExhausted as error:
            return Command(update={"reason": error.reason}, goto="finalize")
        except (ValueError, BrokerError) as error:
            failures.append(
                ToolFailure(
                    tool_name=action.action,
                    code=getattr(error, "code", "INVALID_PROPOSAL"),
                    message=str(error)[:1000],
                ).model_dump()
            )
        # Compare source spans, calculation outputs and metadata coverage. Fresh reference
        # identities alone are not progress, but a new enumeration page is useful discovery.
        registry = await self.registry.load(access, sorted(refs), state["children"])
        fingerprints = registry.progress_fingerprints()
        fresh = fingerprints - set(state["fingerprints"])
        update = {
            "refs": sorted(refs),
            "failures": failures,
            "last_result": result,
            "fingerprints": sorted(fingerprints),
            "stalls": 0 if fresh else state["stalls"] + 1,
        }
        # Post-tool check closes exploration but leaves semantic judgment to the finalizer.
        payload, _ = await self.payload({**state, **update})
        if self.model.input_size(
            "research_finalize", payload, ResearchDraft
        ) + self.limits.final_output_tokens > min(
            self.limits.context_tokens, self.model.context_window
        ):
            update["reason"] = "context_budget"
        return Command(update=update, goto="finalize" if update.get("reason") else "decide")

    async def finalize(self, state):
        payload, registry = await self.payload(state)
        payload["artifact_manifest"] = registry.finalization_manifest(self.counter)
        if state.get("validation_issues"):
            payload["rejected_draft"] = state["rejected_draft"]
            payload["validation_issues"] = state["validation_issues"]
        maximum = self.limits.final_output_tokens
        # Deterministic context selection never manufactures a summary or semantic answer.
        omitted = []
        payload["context_omissions"] = omitted
        for collection in ("last_result", "evidence", "artifacts", "child_claims"):
            while payload[collection] and self.model.input_size(
                "research_finalize", payload, ResearchDraft
            ) + maximum > min(self.limits.context_tokens, self.model.context_window):
                key = next(iter(payload[collection]))
                if collection == "artifacts":
                    key = next(
                        (
                            k
                            for k, v in payload[collection].items()
                            if v["manifest"]["reference_type"] == "collection_query"
                        ),
                        key,
                    )
                payload[collection].pop(key)
                omitted.append(str(key))
        if self.model.input_size("research_finalize", payload, ResearchDraft) + maximum > min(
            self.limits.context_tokens, self.model.context_window
        ):
            raise ValueError("Research finalization context cannot fit")
        draft, _ = await accounting.generate(
            self.model, "research_finalize", payload, ResearchDraft, maximum, final=True
        )
        try:
            envelope = self.registry.finalize(
                registry, state["task_id"], draft, state["reason"], state["failures"]
            )
        except ClaimValidationError as error:
            if state.get("finalization_attempt", 0) >= 1:
                raise
            return Command(
                update={
                    "finalization_attempt": 1,
                    "rejected_draft": draft.model_dump(mode="json"),
                    "validation_issues": error.issues,
                },
                goto="finalize",
            )
        await self.access(state).context.ledger.check(
            self.access(state).context.lease, "finalization"
        )
        return Command(
            update={"result": envelope.model_dump(mode="json"), "waiting": False}, goto=END
        )
