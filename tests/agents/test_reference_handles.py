import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import FinalDraft, KnowledgeWorkerDraftResult
from comtech.agents.model import StructuredModel
from comtech.agents.reference_handles import prepare, translate
from comtech.settings import Settings


def test_final_handles_are_exact_and_leave_prose_and_durable_input_unchanged():
    ref = "d64411cf-056b-49e6-b576-57519ee9c030/task/colombo_195959"
    payload = {"answer_package": {"claims": [{"claim_id": ref, "statement": ref}]}}
    projected, schema, mapping = prepare("final", payload, FinalDraft)
    assert projected["answer_package"]["claims"][0] == {"claim_id": "C1", "statement": ref}
    assert payload["answer_package"]["claims"][0]["claim_id"] == ref
    draft = schema.model_validate(
        {"paragraphs": [{"text": "Converted time.", "claim_ids": ["C1"]}]}
    )
    assert translate(draft.model_dump(), mapping)["paragraphs"][0]["claim_ids"] == [ref]
    with pytest.raises(ValidationError):
        schema.model_validate({"paragraphs": [{"text": "Time.", "claim_ids": ["C9"]}]})


def test_worker_handles_constrain_observations_and_conflicts():
    ref = "OBS-5a7356d48dd66367d32ee3a2"
    payload = {
        "observations": [{"observation_id": ref, "content": "E1043 is primary."}],
        "rejected_draft": {"claims": [{"evidence": [{"observation_id": ref}]}]},
    }
    projected, schema, mapping = prepare("worker_finalize", payload, KnowledgeWorkerDraftResult)
    assert projected["observations"][0]["observation_id"] == "O1"
    assert projected["rejected_draft"]["claims"][0]["evidence"][0]["observation_id"] == "O1"
    draft = {
        "status": "answered",
        "claims": [
            {
                "claim_id": "c2",
                "statement": "E1043 is primary.",
                "support": "direct",
                "evidence": [{"observation_id": "O1", "role": "support"}],
            }
        ],
        "unresolved": [],
        "source_conflicts": [{"description": "Conflict", "observation_ids": ["O1"]}],
    }
    parsed = schema.model_validate(draft)
    restored = KnowledgeWorkerDraftResult.model_validate(translate(parsed.model_dump(), mapping))
    assert restored.claims[0].evidence[0].observation_id == ref
    assert restored.source_conflicts[0].observation_ids == [ref]
    draft["claims"][0]["evidence"][0]["observation_id"] = ref[:-1]
    with pytest.raises(ValidationError):
        schema.model_validate(draft)


async def test_provider_gets_handles_but_application_and_audit_get_durable_ids():
    requests = []

    class Responses:
        async def parse(self, **kwargs):
            requests.append(kwargs)
            return SimpleNamespace(
                status="completed",
                usage=None,
                output_parsed=kwargs["text_format"].model_validate(
                    {"paragraphs": [{"text": "Approved statement.", "claim_ids": ["C1"]}]}
                ),
            )

    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=Responses()),
    )
    payload = {
        "answer_package": {
            "claims": [{"claim_id": "objective/task/claim", "statement": "Approved statement."}]
        }
    }
    result, _ = await model.generate("final", payload, FinalDraft, 1000)
    assert result.paragraphs[0].claim_ids == ["objective/task/claim"]
    assert json.loads(requests[0]["input"])["answer_package"]["claims"][0]["claim_id"] == "C1"
    assert (
        "enum"
        not in FinalDraft.model_json_schema()["$defs"]["RenderedParagraph"]["properties"][
            "claim_ids"
        ]["items"]
    )


async def test_supervisor_handles_restore_claims_citations_and_native_tool_inputs():
    from comtech.research.contracts import SupervisorTurn

    requests = []

    class Responses:
        async def create(self, **kwargs):
            requests.append(kwargs)
            payload = json.loads(kwargs["input"])
            assert payload["task_results"]["research"]["result"]["claims"][0]["claim_id"] == "C1"
            assert payload["available_research_input_refs"] == ["A1"]
            return SimpleNamespace(
                status="completed",
                usage=None,
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="submit_answer",
                        arguments=json.dumps(
                            {
                                "resolved_request": "Count",
                                "claims": [
                                    {
                                        "claim_id": "C1",
                                        "statement": "Count is 4.",
                                        "support": "derived",
                                        "evidence_ids": [],
                                        "source_task_ids": ["research"],
                                        "derivation": "Registered count",
                                        "computation_ref": "A1",
                                        "citations": [{"kind": "computation", "ref": "A1"}],
                                    }
                                ],
                                "unresolved": [],
                                "limitations": [],
                                "source_conflicts": [],
                                "clarification": None,
                            }
                        ),
                    )
                ],
            )

    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=Responses()),
    )
    payload = {
        "task_results": {
            "research": {
                "result": {
                    "claims": [{"claim_id": "obj/task/count", "computation_ref": "ART-existing"}]
                }
            }
        },
        "available_research_input_refs": ["ART-existing"],
        "available_specialists": [],
    }
    result, _ = await model.generate("supervisor", payload, SupervisorTurn, 2000)
    claim = result.decision.answer.claims[0]
    assert claim.claim_id == "obj/task/count"
    assert claim.computation_ref == claim.citations[0].ref == "ART-existing"
    assert payload["available_research_input_refs"] == ["ART-existing"]
