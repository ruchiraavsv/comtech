from copy import deepcopy

from comtech.agents.budget import TokenCounter
from comtech.agents.model_payload import model_payload


def test_projection_preserves_semantic_evidence_and_does_not_mutate_audit_records():
    observation = {
        "observation_id": "OBS-1",
        "evidence_id": "OBS-1",
        "content": "Exact source text",
        "title": "Section",
        "content_hash": "a" * 64,
        "task_id": "original-owner",
        "run_id": "durable-run",
        "retrieved_at": "2026-10-04",
        "token_count": 4,
        "as_of": "2026-09-15",
        "effective_from": "2026-01-01",
        "effective_to": None,
        "is_partial": True,
        "remaining_spans": [[10, 50]],
        "source_ref": {
            "source_id": "DOC-1",
            "version": "1",
            "section_id": "s1",
            "char_start": 0,
            "char_end": 9,
            "record_id": None,
        },
    }
    payload = {"evidence": {"OBS-1": observation}, "observations": [observation]}
    original = deepcopy(payload)
    projected = model_payload("review", payload)
    value = projected["evidence"]["OBS-1"]
    assert value["content"] == observation["content"]
    assert value["source_ref"]["char_end"] == 9
    assert value["as_of"] == "2026-09-15" and value["effective_from"] == "2026-01-01"
    assert value["is_partial"] and value["remaining_spans"] == [[10, 50]]
    assert value["observation_id"] == value["evidence_id"] == "OBS-1"
    assert "content_hash" not in value and "task_id" not in value
    assert projected["observations"] == [value]
    assert payload == original
    assert TokenCounter().count(projected) < TokenCounter().count(original)


def test_only_native_research_schemas_and_identical_task_fields_are_deduplicated():
    payload = {
        "tools": {"read_document_sections": {"parameters": {"maximum": 3}}},
        "sdk_schemas": {
            "read_document_sections": {"maximum": 3},
            "enumerate_documents": {"limit": 100},
        },
        "task": {
            "description": "Question",
            "gap": "Question",
            "expected_output": "Answer",
            "expected_information_gain": "A distinct required gain",
        },
    }
    original = deepcopy(payload)
    projected = model_payload("research", payload)
    assert "tools" not in projected
    assert projected["sdk_schemas"] == {"enumerate_documents": {"limit": 100}}
    assert "gap" not in projected["task"]
    assert projected["task"]["expected_information_gain"] == "A distinct required gain"
    assert model_payload("decision", payload) == original
    assert payload == original
