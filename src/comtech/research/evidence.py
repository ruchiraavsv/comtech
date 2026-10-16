"""Validate trusted research records and export selected claim/premise closures.

R1 uses an in-memory registry boundary with synthetic records. Durable registration
and capability checks belong to R2/R3; model output is never a registry constructor.
"""

from dataclasses import dataclass, field

from comtech.agents.budget import digest
from comtech.agents.contracts import EvidenceRecord
from comtech.agents.errors import ReferenceAuthorizationError, ReferenceSelectionError

from .contracts import (
    AnalysisArtifact,
    ClaimInheritance,
    Coverage,
    ExecutionRecord,
    ExtendedWorkerResult,
    QueryRecord,
    RegisteredClaim,
    SpecialistResult,
)


@dataclass
class EvidenceRegistry:
    run_id: str
    objective_id: str
    parents: dict[str, str | None]
    claims: dict[str, RegisteredClaim] = field(default_factory=dict)
    evidence: dict[str, EvidenceRecord] = field(default_factory=dict)
    queries: dict[str, QueryRecord] = field(default_factory=dict)
    executions: dict[str, ExecutionRecord] = field(default_factory=dict)
    artifacts: dict[str, AnalysisArtifact] = field(default_factory=dict)
    coverage: dict[str, Coverage] = field(default_factory=dict)
    payloads: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    document_handles: set[str] = field(default_factory=set)
    grants: dict[str, set[str]] = field(default_factory=dict)

    def progress_fingerprints(self):
        """New source spans, computations or metadata coverage, independent of receipt IDs."""
        from comtech.agents.budget import serialized

        result = {
            digest(serialized([e.source_ref, e.content_hash])) for e in self.evidence.values()
        }
        result.update(a.result_hash for a in self.artifacts.values())
        for ref, query in self.queries.items():
            cov = self.coverage[query.coverage_ref]
            if ref in self.document_handles or cov.method not in ("aggregate", "enumeration"):
                continue
            result.add(
                digest(
                    serialized(
                        [
                            query.snapshot,
                            cov.method,
                            cov.population_hash,
                            cov.population_definition,
                            cov.total_count,
                            cov.returned_count,
                            cov.enumerated_through,
                        ]
                    )
                )
            )
        return result

    def _owner(self, record, root, reference=None):
        if record.run_id != self.run_id:
            raise ValueError("Cross-run research reference")
        if hasattr(record, "objective_id") and record.objective_id != self.objective_id:
            raise ValueError("Cross-objective research reference")
        if root not in self.parents:
            raise ReferenceAuthorizationError("Unknown research root")
        pending, seen = [root], set()
        while pending:
            task = pending.pop()
            if task == record.task_id or reference in self.grants.get(task, set()):
                return
            if task in seen:
                continue
            seen.add(task)
            pending.extend(t for t, p in self.parents.items() if p == task)
            pending.extend(self.dependencies.get(task, []))
        raise ReferenceAuthorizationError("Invalid task inheritance")

    def lineage(self, reference, root, *, references=None):
        """Resolve every input, preserving exact source bytes and origin task."""
        sources, coverage, executions, artifacts = set(), set(), set(), set()
        visited, active = set(), set()

        def visit(ref):
            if ref in active:
                raise ValueError("Cyclic computation lineage")
            if ref in visited:
                return
            active.add(ref)
            if ref in self.evidence:
                record = self.evidence[ref]
                self._owner(record, root, ref)
                if record.evidence_id != ref or digest(record.content) != record.content_hash:
                    raise ValueError("Source identity or content hash mismatch")
                sources.add(ref)
            elif ref in self.queries or ref in self.artifacts:
                record = self.queries.get(ref) or self.artifacts[ref]
                self._owner(record, root, ref)
                identity = (
                    record.query_ref if isinstance(record, QueryRecord) else record.artifact_ref
                )
                if identity != ref:
                    raise ValueError("Computation identity mismatch")
                payload = self.payloads.get(record.result_ref)
                if payload is None or digest(payload) != record.result_hash:
                    raise ValueError("Result payload missing or content hash mismatch")
                if record.coverage_ref not in self.coverage:
                    raise ValueError("Missing registered coverage")
                cov = self.coverage[record.coverage_ref]
                if cov.coverage_ref != record.coverage_ref:
                    raise ValueError("Coverage identity mismatch")
                coverage.add(record.coverage_ref)
                if isinstance(record, AnalysisArtifact):
                    artifacts.add(ref)
                    execution = self.executions.get(record.execution_ref)
                    if execution is None:
                        raise ValueError("Missing registered execution")
                    # An artifact grant includes its execution proof, never unrelated
                    # outputs of that execution or other records owned by its task.
                    if execution.task_id != record.task_id:
                        raise ValueError("Execution owner differs from artifact owner")
                    self._owner(execution, root, ref)
                    if (
                        execution.execution_ref != record.execution_ref
                        or ref not in execution.output_refs
                    ):
                        raise ValueError("Execution output lineage mismatch")
                    if not record.input_refs or not set(record.input_refs) <= set(
                        execution.input_refs
                    ):
                        raise ValueError("Execution input lineage mismatch")
                    executions.add(execution.execution_ref)
                    for item in record.input_refs:
                        visit(item)
                # Query records establish provenance directly at their pinned source.
                # Coverage may be an aggregate without transferring all rows.
                for item in cov.inspected_refs:
                    if item != ref:
                        visit(item)
            else:
                raise ValueError("Missing registered evidence or computation")
            active.remove(ref)
            visited.add(ref)
            if references is not None:
                references.add(ref)

        visit(reference)
        return sources, coverage, executions, artifacts

    def resolve(self, ref, roots, kind):
        """One authorization/type/integrity boundary for validation and presentation."""
        record = self.evidence.get(ref) or self.queries.get(ref) or self.artifacts.get(ref)
        if record is None:
            raise ReferenceSelectionError(f"Unknown registered reference: {ref}")
        if kind == "source":
            valid_type = ref in self.evidence
        elif kind == "enumeration":
            valid_type = (
                ref in self.queries and self.coverage[record.coverage_ref].method == "enumeration"
            )
        else:
            valid_type = kind == "computation" and ref in self.queries | self.artifacts
        if not valid_type:
            raise ReferenceSelectionError(f"Reference {ref} is not a {kind} citation")
        root = None
        references = set()
        for candidate in roots:
            try:
                candidate_refs = set()
                self.lineage(ref, candidate, references=candidate_refs)
            except ReferenceAuthorizationError:
                continue
            root = candidate
            references = candidate_refs
            break
        if root is None:
            raise ReferenceSelectionError(
                f"Reference {ref} is not authorized under selected source tasks"
            )
        return {
            "kind": kind,
            "ref": ref,
            "origin_task_id": record.task_id,
            "authorized_root": root,
            "lineage_refs": sorted(references),
            "description": self.citation(ref, root) if kind != "source" else None,
        }

    def export(self, result: ExtendedWorkerResult):
        root = result.task_id
        if result.status == "answered" and result.unresolved:
            raise ValueError("Answered result has unresolved required information")
        if result.status == "needs_clarification" and result.clarification is None:
            raise ValueError("Clarification requires a question")
        selected, active = {}, set()
        source_ids, coverages, executions, artifacts = set(), set(), set(), set()

        def add_lineage(ref):
            found = self.lineage(ref, root)
            for target, items in zip(
                (source_ids, coverages, executions, artifacts), found, strict=True
            ):
                target.update(items)

        def visit(key):
            if key in active:
                raise ValueError("Cyclic claim premises")
            if key in selected:
                return
            registered = self.claims.get(key)
            if registered is None:
                raise ValueError("Missing registered claim")
            self._owner(registered, root)
            claim = registered.claim
            if claim.claim_id != key or not key.startswith(
                f"{self.objective_id}/{registered.task_id}/"
            ):
                raise ValueError("Claim identity must preserve its originating task")
            active.add(key)
            if claim.support == "derived" and (
                not claim.derivation or not (claim.premise_claim_ids or claim.computation_ref)
            ):
                raise ValueError("Derived claim lacks premises or registered computation")
            if not any(e.role == "support" for e in claim.evidence) and not claim.computation_ref:
                raise ValueError("Claim lacks supporting evidence")
            for link in claim.evidence:
                # Raw evidence links must never disguise computations as observations.
                if link.evidence_id not in self.evidence:
                    raise ValueError("Missing source evidence")
                add_lineage(link.evidence_id)
            if claim.computation_ref:
                if (
                    claim.support != "derived"
                    or claim.computation_ref not in self.artifacts | self.queries
                ):
                    raise ValueError("Computed claim requires a registered derivation")
                add_lineage(claim.computation_ref)
            for premise in claim.premise_claim_ids:
                visit(premise)
            active.remove(key)
            selected[key] = registered

        if len({c.claim_id for c in result.claims}) != len(result.claims):
            raise ValueError("Duplicate exported claim")
        for claim in result.claims:
            visit(claim.claim_id)
            if claim != selected[claim.claim_id].claim:
                raise ValueError("Export changed a registered claim")
        for conflict in result.source_conflicts:
            for ref in conflict.evidence_ids:
                add_lineage(ref)
        return SpecialistResult(
            specialist="research",
            result=result.model_copy(
                update={"claims": [r.claim.model_copy(deep=True) for r in selected.values()]},
                deep=True,
            ),
            evidence={eid: self.evidence[eid].model_copy(deep=True) for eid in sorted(source_ids)},
            coverage_refs=sorted(coverages),
            execution_refs=sorted(executions),
            artifact_refs=sorted(artifacts),
            inheritance=[
                ClaimInheritance(
                    root_task_id=root,
                    originating_task_id=r.task_id,
                    claim_id=key,
                )
                for key, r in selected.items()
            ],
        )

    def validate_export(self, envelope):
        if self.export(envelope.result) != envelope:
            raise ValueError("Research export does not match registered inheritance and lineage")

    def review_computations(self, counter):
        """Present registered methods, results and input coverage together for review.

        AnalysisProcess is author-reported documentation, not an integrity or completeness
        verdict. Execution metadata and input coverage remain independently registered.
        """
        records = self.queries | self.artifacts
        computations = {}
        for ref, record in records.items():
            if ref in self.document_handles:
                continue  # Keep full lineage in storage; document handles are not findings.
            raw = self.payloads[record.result_ref]
            omitted = counter.count(raw) > 3000
            item = {
                "manifest": record.model_dump(mode="json"),
                "coverage": self.coverage[record.coverage_ref].model_dump(mode="json"),
                "result": None if omitted else raw,
                "result_omitted": omitted,
            }
            if isinstance(record, AnalysisArtifact):
                item["execution"] = self.executions[record.execution_ref].model_dump(mode="json")
                item["input_coverage"] = {
                    key: self.coverage[records[key].coverage_ref].model_dump(mode="json")
                    for key in record.input_refs
                    if key in records
                }
            computations[ref] = item
        return computations

    def finalization_manifest(self, counter):
        """Preserve calculation identities and proof even when bulky context is pruned."""
        manifest = {}
        for ref, record in (self.queries | self.artifacts).items():
            cov = self.coverage[record.coverage_ref]
            if ref in self.document_handles or (ref in self.queries and cov.method == "targeted"):
                continue
            raw = self.payloads[record.result_ref]
            compact = counter.count(raw) <= 512
            item = {
                "reference_type": record.reference_type,
                "result": raw if compact else None,
                "result_omitted": not compact,
                "coverage": {
                    **cov.model_dump(mode="json", exclude={"inspected_refs"}),
                    "inspected_ref_count": len(cov.inspected_refs),
                },
            }
            if isinstance(record, AnalysisArtifact):
                item.update(
                    method=record.method,
                    units=record.units,
                    input_refs=record.input_refs,
                    execution_ref=record.execution_ref,
                    execution_verified=record.execution_ref in self.executions,
                    analysis_process=record.analysis_process.model_dump(mode="json")
                    if record.analysis_process
                    else None,
                )
            manifest[ref] = item
        return manifest

    def citation(self, ref, root):
        from comtech.agents.citations import source_description, source_key

        sources, _, _, _ = self.lineage(ref, root)
        record = self.queries.get(ref) or self.artifacts.get(ref)
        if isinstance(record, QueryRecord):
            description = f"query {ref}, {record.source_id}, snapshot {record.snapshot}"
        elif isinstance(record, AnalysisArtifact):
            description = (
                f"analysis {ref}, execution {record.execution_ref}, method {record.method}"
            )
            if record.units:
                description += f", units {record.units}"
            description += f", {len(record.input_refs)} registered inputs"
        else:
            raise ValueError("Not a computed citation")
        description += f", result {record.result_ref}, SHA256 {record.result_hash}"
        if sources:
            groups = {}
            for key in sorted(sources):
                source = self.evidence[key]
                groups.setdefault(source_key(source), []).append(source)
            description += "; source inputs: " + "; ".join(
                source_description(group) for group in groups.values()
            )
        description += f"; coverage {record.coverage_ref}"
        return description
