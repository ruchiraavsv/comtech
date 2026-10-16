"""Request-local reference handles. Durable records and prose are never rewritten."""

from typing import Literal

from pydantic import create_model

from .contracts import (
    ClaimDraft,
    FinalDraft,
    KnowledgeWorkerDraftResult,
    RenderedParagraph,
    Selection,
    SourceConflictDraft,
)

REFERENCE_FIELDS = {
    "observation_id",
    "observation_ids",
    "evidence_id",
    "evidence_ids",
    "claim_id",
    "claim_ids",
    "premise_claim_ids",
    "inherited_claim_ids",
    "computation_ref",
    "artifact_ref",
    "query_ref",
    "ref",
    "input_refs",
    "inspected_refs",
    "available_research_input_refs",
    "artifact_refs",
}
REFERENCE_MAPS = {"evidence", "artifacts", "child_claims", "artifact_manifest"}


def translate(value, mapping, field=None):
    if isinstance(value, dict):
        return {
            mapping.get(key, key) if field in REFERENCE_MAPS else key: translate(item, mapping, key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [translate(item, mapping, field) for item in value]
    if isinstance(value, str) and field in REFERENCE_FIELDS:
        return mapping.get(value, value)
    return value


def prepare(role, payload, schema):
    groups = []
    if role == "final":
        groups = [
            ("C", [c["claim_id"] for c in payload.get("answer_package", {}).get("claims", [])])
        ]
    elif role == "worker_finalize":
        groups = [("O", [o["observation_id"] for o in payload.get("observations", [])])]
    elif role == "research_finalize":
        groups = [
            ("E", list(payload.get("evidence", {}))),
            (
                "A",
                list(
                    dict.fromkeys(
                        [*payload.get("artifacts", {}), *payload.get("artifact_manifest", {})]
                    )
                ),
            ),
            ("C", list(payload.get("child_claims", {}))),
        ]
    elif role == "supervisor":
        claims = [
            c
            for result in payload.get("task_results", {}).values()
            for c in result.get("result", result).get("claims", [])
        ]
        evidence = list(payload.get("evidence", {}))
        computed = list(
            dict.fromkeys(
                [
                    *(c["computation_ref"] for c in claims if c.get("computation_ref")),
                    *(
                        r
                        for r in payload.get("available_research_input_refs", [])
                        if r not in evidence
                    ),
                ]
            )
        )
        groups = [("C", [c["claim_id"] for c in claims]), ("E", evidence), ("A", computed)]
    mapping = {
        ref: f"{prefix}{i}"
        for prefix, refs in groups
        for i, ref in enumerate(dict.fromkeys(refs), 1)
    }
    wire_schema = schema
    handles = list(mapping.values())
    if handles and role == "final":
        paragraph = create_model(
            "SelectedParagraph",
            __base__=RenderedParagraph,
            claim_ids=(list[Literal[tuple(handles)]], ...),
        )
        wire_schema = create_model(
            "SelectedFinalDraft", __base__=FinalDraft, paragraphs=(list[paragraph], ...)
        )
    elif handles and role == "worker_finalize":
        selection = create_model(
            "ObservedSelection", __base__=Selection, observation_id=(Literal[tuple(handles)], ...)
        )
        claim = create_model("ObservedClaim", __base__=ClaimDraft, evidence=(list[selection], ...))
        conflict = create_model(
            "ObservedConflict",
            __base__=SourceConflictDraft,
            observation_ids=(list[Literal[tuple(handles)]], ...),
        )
        wire_schema = create_model(
            "ObservedDraft",
            __base__=KnowledgeWorkerDraftResult,
            claims=(list[claim], ...),
            source_conflicts=(list[conflict], []),
        )
    data = translate(payload, mapping)
    if mapping:
        data["reference_selection"] = (
            "Select the short reference handles exactly as supplied in this request. "
            "They are request-local; runtime restores durable IDs. Do not copy IDs from prose. "
            "Use handles only in reference fields, not statements or delegated objective prose."
        )
    return data, wire_schema, {handle: ref for ref, handle in mapping.items()}
