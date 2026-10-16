import asyncio

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import (
    ClaimDraft,
    Decision,
    FinalDraft,
    KnowledgeTask,
    KnowledgeWorkerDraftResult,
    RenderedParagraph,
    ReviewDecision,
    Selection,
    SourceRef,
    SupervisorAnswerPackage,
    SupervisorPlan,
    ToolResult,
    UnresolvedItem,
)
from comtech.agents.tools import KnowledgeTools
from comtech.research.contracts import DelegateAction, KnowledgeDelegation, SubmitAction
from comtech.retrieval.store import observation


class FakeTools:
    schemas = {"lookup": {"description": "test lookup", "parameters": {}}}
    failure = staticmethod(KnowledgeTools.failure)

    def __init__(self, *, maximum=3000, fail=False, delay=0):
        self.calls, self.bound, self.fail, self.delay = [], maximum, fail, delay
        self.active = self.peak = 0
        self.entered = asyncio.Event()

    def maximum(self, name):
        return self.bound

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        self.entered.set()
        self.active += 1
        self.peak = max(self.active, self.peak)
        try:
            await asyncio.sleep(self.delay)
            if self.fail:
                return self.failure(name, "UNAVAILABLE", "Test outage")
            identity = arguments.get("id", "service-a")
            return ToolResult(
                observations=[
                    observation(
                        SourceRef(
                            source_type="service_catalog", source_id=identity, version="snapshot"
                        ),
                        "Service",
                        f"{identity} is owned by Team A.",
                        as_of="2026-09-15T10:00:00Z",
                    )
                ]
            )
        finally:
            self.active -= 1


class FakeModel:
    context_window = 128000

    def __init__(self, decisions=1, tasks=1, reject=False, input_size=None):
        self.counter = TokenCounter()
        self.decisions, self.tasks, self.reject = decisions, tasks, reject
        self.fixed_size, self.calls = input_size, []

    def input_size(self, role, payload, schema):
        if self.fixed_size is not None and role == "decision":
            return self.fixed_size
        return self.counter.count(payload) + self.counter.count(schema.model_json_schema()) + 300

    async def generate(self, role, payload, schema, max_output_tokens):
        self.calls.append((role, payload, max_output_tokens))
        if role == "supervisor":
            missing = [
                KnowledgeTask(task_id=f"task-{i}", objective="Find current owner")
                for i in range(self.tasks)
                if f"task-{i}" not in payload["task_results"]
            ]
            missing += [
                KnowledgeTask.model_validate(t)
                for t in payload["review"].get("followup_tasks", [])
                if t["task_id"] not in payload["task_results"]
            ]
            if missing:
                value = schema(
                    decision=DelegateAction(
                        resolved_request="Who owns the services?",
                        calls=[KnowledgeDelegation(task=t) for t in missing],
                    )
                )
            else:
                package, _ = await self.generate(
                    "synthesize", payload, SupervisorAnswerPackage, max_output_tokens
                )
                value = schema(decision=SubmitAction(answer=package))
        elif role == "decision":
            value = (
                Decision(
                    action="tool",
                    tool_name="lookup",
                    arguments_json='{"id":"' + payload["task"]["task_id"] + '"}',
                )
                if (payload["cycle"] < self.decisions)
                else Decision(action="finalize")
            )
        elif role == "worker_finalize":
            obs = payload["observations"]
            partial = payload["termination_reason"] != "completed"
            value = KnowledgeWorkerDraftResult(
                status="partial" if partial or not obs else "answered",
                claims=[
                    ClaimDraft(
                        claim_id="owner",
                        statement=o["content"],
                        support="direct",
                        evidence=[Selection(observation_id=o["observation_id"])],
                    )
                    for o in obs[:1]
                ],
                unresolved=[
                    UnresolvedItem(
                        information_need="Replication mode",
                        reason="insufficient_evidence",
                        details="The inspected sections did not establish "
                        "replication mode; exploration ended due to "
                        + payload["termination_reason"],
                    )
                ]
                if partial or not obs
                else [],
            )
        elif role == "plan":
            value = SupervisorPlan(
                resolved_request="Who owns the services?",
                tasks=[
                    KnowledgeTask(task_id=f"task-{i}", objective="Find current owner")
                    for i in range(self.tasks)
                ],
            )
        elif role == "synthesize":
            claims = []
            unresolved = []
            for task_id, result in payload["task_results"].items():
                unresolved.extend(result["unresolved"])
                for c in result["claims"]:
                    claims.append(
                        {
                            "claim_id": c["claim_id"],
                            "statement": c["statement"],
                            "support": c["support"],
                            "evidence_ids": [e["evidence_id"] for e in c["evidence"]],
                            "source_task_ids": [task_id],
                        }
                    )
            value = schema(
                resolved_request=payload["resolved_request"],
                claims=claims,
                unresolved=unresolved,
                limitations=[],
                source_conflicts=[],
                clarification=None,
            )
        elif role == "review":
            value = ReviewDecision(
                status="revise_supervisor" if self.reject else "approved",
                issues=[],
                required_changes=["Repair"] if self.reject else [],
                followup_tasks=[],
            )
        elif role == "final":
            value = FinalDraft(
                paragraphs=[
                    RenderedParagraph(text=c["statement"], claim_ids=[c["claim_id"]])
                    for c in payload["answer_package"]["claims"]
                ]
            )
        else:
            raise AssertionError(role)
        return schema.model_validate(value), {"input_tokens": 20, "output_tokens": 10}
