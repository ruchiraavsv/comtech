"""Validate selected observations and materialize only their exact content."""

from .budget import digest, serialized
from .citations import computation_refs, resolve_citations, selections
from .contracts import (
    ClaimEvidenceLink,
    EvidenceRecord,
    KnowledgeWorkerResult,
    SourceConflict,
    SupportedClaim,
)
from .errors import ClaimValidationError


def validate_premises(claims, external=(), computations=(), observed=None):
    indexed = {c.claim_id: c for c in claims}
    issues = []

    def issue(key, field, message):
        issues.append({"claim_id": key, "field": field, "message": message})

    if len(indexed) != len(claims):
        issue("claims", "claim_id", "Duplicate claim IDs; assign unique local IDs.")
    for claim in claims:
        key = claim.claim_id
        refs = (
            computation_refs(claim)
            if hasattr(claim, "citations")
            else ([claim.computation_ref] if getattr(claim, "computation_ref", None) else [])
        )
        computation = bool(refs)
        if set(refs) - set(computations):
            issue(
                key,
                "computation_ref",
                "Unregistered computation reference; select a registered one.",
            )
        if computation and claim.support != "derived":
            issue(key, "support", "Computed claim requires a registered derivation.")
        if claim.support == "derived":
            if not (claim.premise_claim_ids or computation):
                issue(
                    key,
                    "premise_claim_ids",
                    "Derived claim lacks premises or derivation: "
                    "select supporting claim IDs or a registered computation. Observation IDs "
                    "are not premise claim IDs. Split an observed fact into a direct premise "
                    "when needed; do not invent support.",
                )
            if not claim.derivation or not claim.derivation.strip():
                issue(
                    key,
                    "derivation",
                    "Derived claim lacks premises or derivation: "
                    "explain how the selected premises or computation support this conclusion.",
                )
        for premise in claim.premise_claim_ids:
            if premise not in indexed and premise not in external:
                issue(key, "premise_claim_ids", f"Unknown premise claim: {premise}.")
        if observed is not None:
            if not computation and not any(e.role == "support" for e in claim.evidence):
                issue(
                    key,
                    "evidence",
                    "Claim lacks selected supporting evidence. Select observed "
                    "support, or move the unsupported information need to unresolved.",
                )
            for link in claim.evidence:
                ref = getattr(link, "observation_id", None) or getattr(link, "evidence_id", None)
                if ref not in observed:
                    issue(
                        key,
                        "evidence",
                        f"Selected evidence was not observed: {ref}. "
                        f"Allowed references: {', '.join(sorted(observed))}.",
                    )
    visited, active = set(), set()

    def visit(key):
        if key in active:
            issue(key, "premise_claim_ids", "Cyclic claim premises; remove circular support.")
            return
        if key in visited or key in external:
            return
        if key not in indexed:
            return
        active.add(key)
        claim = indexed[key]
        for premise in claim.premise_claim_ids:
            visit(premise)
        active.remove(key)
        visited.add(key)

    for key in indexed:
        visit(key)
    if issues:
        raise ClaimValidationError(issues)


def materialize(draft, observations, run_id, task_id, reason, failures):
    validate_premises(draft.claims, observed=observations)
    if draft.status == "needs_clarification" and draft.clarification is None:
        raise ValueError("Clarification status requires a question")
    if draft.status == "answered" and draft.unresolved:
        raise ValueError("Answered result cannot hide unresolved required information")
    selected = {e.observation_id for claim in draft.claims for e in claim.evidence}
    selected.update(oid for conflict in draft.source_conflicts for oid in conflict.observation_ids)
    if not selected.issubset(observations):
        raise ValueError("Selected evidence was not observed by this worker")
    evidence, lookup = {}, {}
    for oid in sorted(selected):
        item = observations[oid]
        if digest(item.content) != item.content_hash:
            raise ValueError("Observed content hash mismatch")
        eid = "EV-" + digest(serialized([run_id, task_id, item.source_ref, item.content_hash]))[:24]
        evidence[eid] = EvidenceRecord(
            **item.model_dump(), evidence_id=eid, run_id=run_id, task_id=task_id
        )
        lookup[oid] = eid
    claims = []
    for claim in draft.claims:
        if not claim.evidence or not any(e.role == "support" for e in claim.evidence):
            raise ValueError("Claim lacks selected supporting evidence")
        claims.append(
            SupportedClaim(
                claim_id=f"{task_id}:{claim.claim_id}",
                statement=claim.statement,
                support=claim.support,
                evidence=[
                    ClaimEvidenceLink(evidence_id=lookup[e.observation_id], role=e.role)
                    for e in claim.evidence
                ],
                premise_claim_ids=[f"{task_id}:{key}" for key in claim.premise_claim_ids],
                derivation=claim.derivation,
            )
        )
    # New global stop reasons are explicit version-2 results; old checkpoints keep
    # their original wire contract. Semantic status still comes from the LLM.
    from comtech.research.contracts import ExtendedWorkerResult

    result_type = (
        ExtendedWorkerResult
        if reason in ("objective_budget", "deadline")
        else KnowledgeWorkerResult
    )
    result = result_type(
        task_id=task_id,
        status=draft.status,
        termination_reason=reason,
        claims=claims,
        unresolved=draft.unresolved,
        clarification=draft.clarification,
        tool_failures=failures,
        source_conflicts=[
            SourceConflict(
                description=c.description, evidence_ids=[lookup[oid] for oid in c.observation_ids]
            )
            for c in draft.source_conflicts
        ],
    )
    return result, evidence


def validate_package(package, results, evidence, registry=None):
    from comtech.research.contracts import SpecialistResult

    computations = set()
    resolved = {}
    for key, result in results.items():
        if isinstance(result, SpecialistResult):
            if registry is None or result.specialist != "research":
                raise ValueError("Research result requires its trusted registry")
            registry.validate_export(result)
            if any(
                eid not in evidence or EvidenceRecord.model_validate(evidence[eid]) != record
                for eid, record in result.evidence.items()
            ):
                raise ValueError("Research evidence changed after export")
            resolved[key] = result.result
            computations.update(
                c.computation_ref for c in result.result.claims if c.computation_ref
            )
        else:
            if any(c.computation_ref for c in result.claims):
                raise ValueError("Ordinary worker cannot register computations")
            resolved[key] = result
        if resolved[key].task_id != key:
            raise ValueError("Result task identity mismatch")
    results = resolved
    worker_claims = {c.claim_id: c for r in results.values() for c in r.claims}
    # Reused IDs must still undergo cycle validation if present in the package.
    answer_ids = {c.claim_id for c in package.claims}
    validate_premises(package.claims, set(worker_claims) - answer_ids, computations)
    issues = []
    for claim in package.claims:

        def issue(field, message, claim_id=claim.claim_id):
            issues.append({"claim_id": claim_id, "field": field, "message": message})

        selected = selections(claim)
        source_ids = {c.ref for c in selected if c.kind == "source"}
        if not source_ids and not computation_refs(claim):
            issue(
                "evidence_ids",
                "No evidence_ids selected. Even a derived answer claim must "
                "select supporting evidence IDs from its source tasks, or a registered "
                "computation_ref. Premise IDs alone do not supply its rendered citations.",
            )
        missing = source_ids - evidence.keys()
        if missing:
            issue("evidence_ids", "Missing evidence IDs: " + ", ".join(sorted(missing)))
        if not claim.source_task_ids or not set(claim.source_task_ids).issubset(results):
            issue("source_task_ids", "Answer claim references missing task")
            continue
        available = {
            link.evidence_id
            for tid in claim.source_task_ids
            for c in results[tid].claims
            for link in c.evidence
        }
        if not source_ids.issubset(available):
            issue("evidence_ids", "Answer evidence does not belong to the selected tasks")
        if computation_refs(claim):
            owned = {
                c.computation_ref for tid in claim.source_task_ids for c in results[tid].claims
            }
            if claim.support != "derived" or not set(computation_refs(claim)) <= owned:
                issue("computation_ref", "Answer computation does not belong to selected tasks")
        if claim.claim_id not in worker_claims and claim.support != "derived":
            issue("support", "New supervisor claim must be explicitly derived")
    if issues:
        raise ClaimValidationError(issues)
    for conflict in package.source_conflicts:
        if not set(conflict.evidence_ids).issubset(evidence):
            raise ValueError("Conflict references missing evidence")
    return resolve_citations(package, evidence, registry)
