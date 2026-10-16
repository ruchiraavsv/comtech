"""Opt-in Supervisor integration. Waiting yields the durable parent task slot."""

from langgraph.types import interrupt

from . import accounting
from .access import Access, subset
from .actions import ChildProposal
from .broker_contracts import OPERATIONS
from .contracts import ExtendedWorkerResult, SourceScope, SpecialistResult


class ResearchSpecialist:
    def __init__(self, agent, store=None):
        self.agent = agent
        self.store = store or getattr(getattr(agent.broker, "documents", None), "store", None)

    async def access(self):
        context = accounting.CURRENT.get()
        if context is None:
            raise ValueError("Research requires background accounting")
        objective = await context.ledger.check(context.lease, "finalization")
        scope = SourceScope.model_validate(objective["scope"])
        scope = scope.model_copy(
            update={
                "sources": ["documents"],
                "datasets": {"documents": scope.datasets.get("documents", [])},
                "fields": {"documents": scope.fields.get("documents", [])},
                "capabilities": [c for c in scope.capabilities if c in OPERATIONS],
                "pinned_versions": {"documents": scope.pinned_versions["documents"]},
            }
        )
        return Access(context, scope, None, "")

    async def retain(self, state):
        if not state.get("research_bindings"):
            return {}
        registry = await self.validate(state["research_bindings"], state["task_results"])
        selected = {r for c in state["answer_package"]["claims"] for r in c["evidence_ids"]}
        selected.intersection_update(registry.evidence)
        computed = {
            c["computation_ref"]
            for c in state["answer_package"]["claims"]
            if c.get("computation_ref")
        }
        visited = set()

        def premises(key):
            if key in visited or key not in registry.claims:
                return
            visited.add(key)
            claim = registry.claims[key].claim
            selected.update(e.evidence_id for e in claim.evidence)
            if claim.computation_ref:
                computed.add(claim.computation_ref)
            for premise in claim.premise_claim_ids:
                premises(premise)

        for claim in state["answer_package"]["claims"]:
            premises(claim["claim_id"])
        for conflict in state["answer_package"].get("source_conflicts", []):
            selected.update(r for r in conflict["evidence_ids"] if r in registry.evidence)
        selected.update(computed)
        selected.update(
            citation["ref"]
            for claim in state["answer_package"]["claims"]
            for citation in claim.get("citations", [])
        )
        access = await self.access()
        if hasattr(self.agent.broker, "retain"):
            await self.agent.broker.retain(access, selected)
        else:
            await self.agent.broker.artifacts.retain(access, selected)
        return {"selected_refs": sorted(selected), "computation_refs": sorted(computed)}

    async def admit(self, request):
        access = await self.access()
        await self.agent.broker.capabilities.register_scope(access.context.lease, access.scope)
        scope = access.scope
        if request.document_ids is not None:
            if self.store is None or self.store.build_id != scope.pinned_versions["documents"]:
                raise ValueError("Document selector validation requires the pinned source manifest")
            try:
                selectors = list(
                    dict.fromkeys(self.store.resolve_document_id(s) for s in request.document_ids)
                )
            except ValueError:
                raise ValueError(
                    "Unrecognized document_ids. Use exact published IDs or document_ids=null "
                    "to discover the requested documents within inherited scope."
                ) from None
            scope = scope.model_copy(update={"document_ids": selectors})
            subset(scope, access.scope)
        proposal = ChildProposal(
            description=request.objective,
            expected_output=request.expected_output,
            analysis_mode=request.analysis_mode,
            narrowed_scope=scope,
            input_refs=request.input_refs,
            partition="supervisor:" + request.task_id,
            gap=request.objective,
            reason="Supervisor delegation",
            expected_information_gain=request.expected_output,
        )
        tasks = await self.agent.admission.propose(access.context.lease, [proposal])
        return str(tasks[0])

    async def collect(self, bindings):
        access = await self.access()
        tasks = {alias: await self.agent.queue.get(task_id) for alias, task_id in bindings.items()}
        pending = [
            str(t["id"])
            for t in tasks.values()
            if t["state"] not in ("completed", "failed", "cancelled")
        ]
        if pending:
            interrupt({"research_wait": pending})
            # Resume input carries no trusted result; re-read durable state.
            return await self.collect(bindings)
        for task in tasks.values():
            if task["state"] != "completed":
                continue
            envelope = SpecialistResult.model_validate(task["result"])
            refs = set(envelope.evidence) | set(envelope.artifact_refs)
            refs.update(c.computation_ref for c in envelope.result.claims if c.computation_ref)
            for ref in refs:
                await self.agent.broker.records.grant(
                    access.context.lease, ref, access.context.lease.task_id
                )
        registry = await self.agent.registry.load(access, child_ids=bindings.values())
        envelopes = {}
        for alias, task in tasks.items():
            if alias in registry.parents:
                raise ValueError("Supervisor alias collides with canonical task identity")
            registry.parents[alias] = str(access.context.lease.task_id)
            registry.dependencies[alias] = [str(task["id"])]
            if task["state"] == "completed":
                result = SpecialistResult.model_validate(task["result"]).result.model_copy(
                    update={"task_id": alias}
                )
            else:
                # A failed follow-up cannot invalidate an independently validated result.
                # Export only its durable failure, never its unvalidated draft or evidence.
                message = (
                    f"Research task {alias} {task['state']} without a validated result "
                    f"({task['termination_reason']}). This does not establish source absence."
                )
                result = ExtendedWorkerResult(
                    task_id=alias,
                    status="partial",
                    termination_reason="tool_failure",
                    claims=[],
                    unresolved=[
                        {
                            "information_need": task["input"]["description"],
                            "reason": "insufficient_evidence",
                            "details": message,
                        }
                    ],
                    source_conflicts=[],
                    clarification=None,
                    tool_failures=[
                        {
                            "tool_name": "research",
                            "code": task["state"],
                            "message": message,
                        }
                    ],
                )
            envelopes[alias] = registry.export(result)
        return registry, envelopes

    async def validate(self, bindings, saved):
        registry, envelopes = await self.collect(bindings)
        for alias, envelope in envelopes.items():
            if envelope != SpecialistResult.model_validate(saved[alias]):
                raise ValueError("Checkpoint Research export differs from durable selected closure")
        return registry
