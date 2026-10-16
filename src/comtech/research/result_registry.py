"""Hydrate R1's validation/export boundary from durable broker records.

Models select registered identities; they never supply provenance or task ownership.
Only the selected closure is exported. Large immutable source data stays in storage.
"""

import asyncio

from comtech.agents.budget import digest, serialized
from comtech.agents.contracts import EvidenceRecord, Observation
from comtech.agents.errors import ClaimValidationError
from comtech.agents.evidence import validate_premises

from .contracts import (
    AnalysisArtifact,
    Coverage,
    ExecutionRecord,
    ExtendedWorkerResult,
    QueryRecord,
    RegisteredClaim,
    SpecialistResult,
)
from .evidence import EvidenceRegistry


class ResultRegistry:
    def __init__(self, broker):
        self.broker, self.pool = broker, broker.capabilities.pool

    async def load(self, access, refs=(), child_ids=()):
        lease = access.context.lease
        objective = await access.context.ledger.check(lease, "finalization")
        async with self.pool.connection() as conn:
            tasks = await (
                await conn.execute(
                    "SELECT * FROM research_tasks WHERE objective_id=%s",
                    (lease.objective_id,),
                )
            ).fetchall()
            edges = await (
                await conn.execute(
                    "SELECT parent_id,child_id FROM research_dependencies WHERE objective_id=%s",
                    (lease.objective_id,),
                )
            ).fetchall()
            grants = await (
                await conn.execute(
                    "SELECT g.ref,g.task_id FROM research_data_grants g "
                    "JOIN research_data_records r ON r.ref=g.ref WHERE r.objective_id=%s",
                    (lease.objective_id,),
                )
            ).fetchall()
        index = {str(t["id"]): t for t in tasks}
        registry = EvidenceRegistry(
            str(objective["run_id"]),
            str(lease.objective_id),
            {k: str(t["parent_id"]) if t["parent_id"] else None for k, t in index.items()},
        )
        for edge in edges:
            registry.dependencies.setdefault(str(edge["parent_id"]), []).append(
                str(edge["child_id"])
            )
        for grant in grants:
            if str(grant["task_id"]) in index:
                registry.grants.setdefault(str(grant["task_id"]), set()).add(grant["ref"])
        seen, active = set(), set()

        async def visit(ref):
            if ref in active:
                raise ValueError("Cyclic durable evidence lineage")
            if ref in seen:
                return
            active.add(ref)
            row = await self.broker.records.get(access, ref)
            payload, cov = row["payload"], row["coverage"]
            for item in row["input_refs"]:
                await visit(item)
            if row["kind"] == "observation":
                observation = Observation.model_validate(payload)
                registry.evidence[ref] = EvidenceRecord(
                    **observation.model_dump(),
                    evidence_id=ref,
                    run_id=registry.run_id,
                    task_id=str(row["task_id"]),
                )
            elif row["kind"] in ("artifact", "page", "document"):
                if row["kind"] == "document":
                    registry.document_handles.add(ref)
                coverage_ref = "COV-" + ref
                registry.coverage[coverage_ref] = Coverage(
                    coverage_ref=coverage_ref,
                    requested_scope_ref=row["source_scope"]["scope_ref"],
                    inspected_refs=row["input_refs"],
                    method="aggregate"
                    if row["kind"] == "artifact" or cov.get("method") == "aggregate"
                    else "enumeration"
                    if cov.get("method") == "enumeration"
                    else "targeted",
                    population_definition=serialized(cov.get("population_definition"))
                    if cov.get("population_definition") is not None
                    else None,
                    population_hash=cov.get("population_hash"),
                    total_count=cov.get("total_count"),
                    truncated=payload.get("truncated", cov.get("truncated", False)),
                    cursor=payload.get("next_cursor"),
                    returned_count=cov.get("returned_count"),
                    enumerated_through=cov.get("enumerated_through"),
                    population_complete=cov.get("population_complete", False),
                    semantic_inspection=cov.get("semantic_inspection"),
                    pinned_versions=row["source_scope"]["pinned_versions"],
                    relevant_omissions=[cov["note"]] if cov.get("note") else [],
                )
                value = payload
                if row["kind"] == "artifact":
                    value = (
                        await self.broker.artifact_value(access, row)
                        if hasattr(self.broker, "artifact_value")
                        else await asyncio.to_thread(self.broker.artifacts.load, row)
                    )
                value_ref = ref + ":result"
                registry.payloads[value_ref] = serialized(value)
                common = dict(
                    run_id=registry.run_id,
                    objective_id=registry.objective_id,
                    task_id=str(row["task_id"]),
                    result_ref=value_ref,
                    result_hash=digest(registry.payloads[value_ref]),
                    coverage_ref=coverage_ref,
                )
                if row["kind"] == "artifact":
                    async with self.pool.connection() as conn:
                        execution = await (
                            await conn.execute(
                                "SELECT * FROM research_executions WHERE id=%s AND objective_id=%s",
                                (row["execution_id"], lease.objective_id),
                            )
                        ).fetchone()
                    if not execution or execution["state"] != "success":
                        raise ValueError("Artifact execution did not complete successfully")
                    if str(execution["task_id"]) != str(row["task_id"]):
                        raise ValueError("Artifact execution owner mismatch")
                    record = execution["record"]
                    if payload["code_hash"] != record.get("code_hash") or payload[
                        "environment_digest"
                    ] != record.get("environment_digest"):
                        raise ValueError("Artifact execution provenance mismatch")
                    if payload.get("analysis_provenance", {}) != record.get(
                        "analysis_provenance", {}
                    ):
                        raise ValueError("Artifact analysis provenance mismatch")
                    execution_ref = str(execution["id"])
                    previous = registry.executions.get(execution_ref)
                    registry.executions[execution_ref] = ExecutionRecord(
                        execution_ref=execution_ref,
                        run_id=registry.run_id,
                        objective_id=registry.objective_id,
                        task_id=str(row["task_id"]),
                        code_hash=record["code_hash"],
                        environment_digest=record["environment_digest"],
                        input_refs=sorted(
                            set(row["input_refs"]) | set(previous.input_refs if previous else [])
                        ),
                        output_refs=[*(previous.output_refs if previous else []), ref],
                        started_at=record["started_at"],
                        finished_at=record["finished_at"],
                        limits=record["limits"],
                    )
                    registry.artifacts[ref] = AnalysisArtifact(
                        **common,
                        artifact_ref=ref,
                        execution_ref=execution_ref,
                        method=payload["method"],
                        input_refs=row["input_refs"],
                        units=payload["units"],
                        assumptions=payload["assumptions"],
                        extraction_version=payload.get("extraction_version"),
                        analysis_provenance=payload.get("analysis_provenance", {}),
                        analysis_process=payload.get("analysis_process"),
                    )
                else:
                    registry.queries[ref] = QueryRecord(
                        **common,
                        query_ref=ref,
                        source_id="documents",
                        snapshot=row["source_scope"]["pinned_versions"]["documents"],
                        normalized_query=serialized(cov),
                        selected_fields=row["source_scope"]["fields"].get("documents", []),
                    )
            active.remove(ref)
            seen.add(ref)

        for ref in refs:
            await visit(ref)
        for child_id in child_ids:
            child = index[str(child_id)]
            if child["state"] != "completed" or not child["result"]:
                continue
            envelope = SpecialistResult.model_validate(child["result"])
            owners = {i.claim_id: i.originating_task_id for i in envelope.inheritance}
            for claim in envelope.result.claims:
                registry.claims[claim.claim_id] = RegisteredClaim(
                    run_id=registry.run_id,
                    objective_id=registry.objective_id,
                    task_id=owners[claim.claim_id],
                    claim=claim,
                )
                for link in claim.evidence:
                    await visit(link.evidence_id)
                if claim.computation_ref:
                    await visit(claim.computation_ref)
            for conflict in envelope.result.source_conflicts:
                for ref in conflict.evidence_ids:
                    await visit(ref)
            registry.validate_export(envelope)
        return registry

    def finalize(self, registry, task_id, draft, reason, failures):
        issues = [
            {
                "claim_id": c.claim_id,
                "field": "claim_id",
                "message": "New claims require short local IDs without '/'. Select existing "
                "child claims only through inherited_claim_ids; do not copy them into claims.",
            }
            for c in draft.claims
            if "/" in c.claim_id
        ]
        issues.extend(
            {
                "claim_id": key,
                "field": "inherited_claim_ids",
                "message": "Unregistered inherited claim; select an exact child_claims key.",
            }
            for key in draft.inherited_claim_ids
            if key not in registry.claims
        )
        if issues:
            raise ClaimValidationError(issues)
        validate_premises(
            draft.claims,
            registry.claims,
            registry.artifacts | registry.queries,
            observed=registry.evidence,
        )
        prefix = f"{registry.objective_id}/{task_id}/"
        local = {c.claim_id: prefix + c.claim_id for c in draft.claims}
        selected = []
        for key in draft.inherited_claim_ids:
            selected.append(registry.claims[key].claim)
        for claim in draft.claims:
            claim = claim.model_copy(
                update={
                    "claim_id": local[claim.claim_id],
                    "premise_claim_ids": [local.get(p, p) for p in claim.premise_claim_ids],
                }
            )
            registry.claims[claim.claim_id] = RegisteredClaim(
                run_id=registry.run_id,
                objective_id=registry.objective_id,
                task_id=task_id,
                claim=claim,
            )
            selected.append(claim)
        # Draft conflict observation IDs are exact registered evidence identities.
        result = ExtendedWorkerResult(
            task_id=task_id,
            status=draft.status,
            termination_reason=reason,
            claims=selected,
            unresolved=draft.unresolved,
            clarification=draft.clarification,
            tool_failures=failures,
            source_conflicts=[
                {"description": c.description, "evidence_ids": c.observation_ids}
                for c in draft.source_conflicts
            ],
        )
        return registry.export(result)
