"""Compact source groups without merging versions, snapshots or exact locators."""

import json

from .budget import digest
from .contracts import CitationSelection, EvidenceRecord
from .errors import ClaimValidationError, ReferenceSelectionError


def selections(claim):
    """Typed selections plus compatibility with existing checkpoints."""
    selected = [CitationSelection(kind="source", ref=r) for r in claim.evidence_ids]
    if claim.computation_ref:
        selected.append(CitationSelection(kind="computation", ref=claim.computation_ref))
    selected.extend(claim.citations)
    return list({(c.kind, c.ref): c for c in selected}.values())


def computation_refs(claim):
    return [c.ref for c in selections(claim) if c.kind == "computation"]


def resolve_citations(package, evidence, registry=None):
    """Resolve before review and use the same plan when rendering approved claims."""
    plan, issues = {}, []
    for claim in package.claims:
        resolved = {}
        for citation in selections(claim):
            try:
                if citation.kind == "source":
                    if citation.ref not in evidence:
                        raise ReferenceSelectionError(f"Missing evidence IDs: {citation.ref}")
                    record = EvidenceRecord.model_validate(evidence[citation.ref])
                    if (
                        record.evidence_id != citation.ref
                        or digest(record.content) != record.content_hash
                    ):
                        raise ValueError("Source identity or content hash mismatch")
                    item = {
                        "kind": "source",
                        "ref": citation.ref,
                        "origin_task_id": record.task_id,
                        "description": source_description([record]),
                    }
                    if registry and citation.ref in registry.evidence:
                        item.update(registry.resolve(citation.ref, claim.source_task_ids, "source"))
                        item["description"] = source_description([record])
                    elif record.task_id not in claim.source_task_ids:
                        raise ReferenceSelectionError(
                            f"Source {citation.ref} is not owned by a selected source task"
                        )
                else:
                    if registry is None:
                        raise ValueError("Computed citation requires a trusted registry")
                    item = registry.resolve(citation.ref, claim.source_task_ids, citation.kind)
                    # Show enumeration inputs explicitly, not only an opaque artifact ID.
                    for ref in item["lineage_refs"]:
                        query = registry.queries.get(ref)
                        if query and registry.coverage[query.coverage_ref].method == "enumeration":
                            resolved[("enumeration", ref)] = registry.resolve(
                                ref, [item["authorized_root"]], "enumeration"
                            )
                resolved[(citation.kind, citation.ref)] = item
            except ReferenceSelectionError as error:
                issues.append(
                    {"claim_id": claim.claim_id, "field": "citations", "message": str(error)}
                )
        plan[claim.claim_id] = list(resolved.values())
    if issues:
        raise ClaimValidationError(issues)
    return plan


def source_key(record):
    ref = record.source_ref
    # Operational collections reuse record IDs across filters. Keep distinct query
    # results separate, especially an empty result versus a populated result.
    query_identity = record.content_hash if ref.source_type != "document" else None
    return (
        ref.source_type,
        ref.source_id,
        ref.version,
        ref.record_id,
        record.as_of,
        query_identity,
    )


def source_description(records):
    first = records[0]
    ref = first.source_ref
    label = f"{ref.source_id}, version {ref.version}"
    if ref.record_id:
        label += f", record {ref.record_id}"
    if first.as_of:
        label += f", as of {first.as_of}"
    if ref.source_type != "document":
        try:
            content = json.loads(first.content)
        except (ValueError, TypeError):
            content = {}
        query = content.get("_query") if isinstance(content, dict) else None
        if isinstance(query, dict) and isinstance(query.get("arguments"), dict):
            arguments = ", ".join(
                f"{key}={json.dumps(value, ensure_ascii=False)}"
                for key, value in sorted(query["arguments"].items())
            )
            label += f"; {query.get('tool', 'query')}({arguments})"
    locators = []
    for record in sorted(
        records, key=lambda r: (r.source_ref.section_id or "", r.source_ref.char_start or 0)
    ):
        source = record.source_ref
        locator = ""
        if source.section_id:
            # Only shorten the mechanically reconstructible document/version prefix.
            section = source.section_id.removeprefix(f"{source.source_id}:v{source.version}:")
            locator = section
        if source.char_start is not None:
            locator += f" (characters {source.char_start}–{source.char_end})"
        if locator.strip() and locator.strip() not in locators:
            locators.append(locator.strip())
    if locators:
        label += "; " + "; ".join(locators)
    return label
