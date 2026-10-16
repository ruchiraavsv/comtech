from comtech.agents.contracts import FinalDraft, SupervisorAnswerPackage
from comtech.agents.graph import render
from tests.research.test_evidence import fixture, package


def test_different_operational_query_scopes_never_share_a_citation():
    import json

    from comtech.agents.budget import digest

    registry, result = fixture()
    base = registry.evidence["EV-source"].model_dump(mode="json")
    base["task_id"] = "root"  # Ordinary source owned by the selected task.
    evidence = {}
    for service in ("payflow", "notifyhub"):
        content = json.dumps(
            {
                "_query": {"tool": "list_open_incidents", "arguments": {"service_id": service}},
                "items": [],
            }
        )
        evidence[service] = {
            **base,
            "evidence_id": service,
            "content": content,
            "content_hash": digest(content),
            "source_ref": {
                "source_type": "incident_record",
                "source_id": "northstar:open_incidents",
                "record_id": "open_incidents",
                "version": "snapshot",
            },
        }
    answer = package(result.claims[0], list(evidence))
    draft = FinalDraft(
        paragraphs=[{"text": "Scoped empty results.", "claim_ids": [answer.claims[0].claim_id]}]
    )
    text = render(draft, answer, evidence)
    assert text.splitlines()[0] == "Scoped empty results. [1] [2]"
    assert 'service_id="payflow"' in text and 'service_id="notifyhub"' in text


def test_grouped_citations_keep_every_locator_and_separate_versions_and_snapshots():
    registry, result = fixture()
    base = registry.evidence["EV-source"].model_dump(mode="json")
    base["task_id"] = "root"
    evidence = {}
    for index, (version, section, as_of) in enumerate(
        [("1", "01", "old"), ("1", "02", "old"), ("2", "01", "old"), ("1", "01", "new")]
    ):
        evidence[f"e{index}"] = {
            **base,
            "evidence_id": f"e{index}",
            "as_of": as_of,
            "source_ref": {
                **base["source_ref"],
                "version": version,
                "section_id": f"synthetic:v{version}:section-{section}",
                "char_start": index * 100,
                "char_end": index * 100 + 9,
            },
        }
    answer = package(result.claims[0], list(evidence))
    draft = FinalDraft(
        paragraphs=[{"text": "Supported comparison.", "claim_ids": [answer.claims[0].claim_id]}]
    )
    text = render(draft, answer, evidence)
    assert text.splitlines()[0] == "Supported comparison. [1] [2] [3]"
    assert text.count("synthetic, version") == 3
    assert "section-01 (characters 0–9); section-02 (characters 100–109)" in text
    assert "version 2, as of old; section-01 (characters 200–209)" in text
    assert "version 1, as of new; section-01 (characters 300–309)" in text
    assert evidence["e0"]["source_ref"]["section_id"] == "synthetic:v1:section-01"


def test_multiple_paragraphs_share_source_number_without_losing_selected_spans():
    registry, result = fixture()
    first = registry.evidence["EV-source"].model_dump(mode="json")
    first["task_id"] = "root"
    second = {
        **first,
        "evidence_id": "second",
        "source_ref": {
            **first["source_ref"].copy(),
            "section_id": "s2",
            "char_start": 10,
            "char_end": 20,
        },
    }
    answer = package(result.claims[0], ["EV-source"])
    answer = SupervisorAnswerPackage.model_validate(
        {
            **answer.model_dump(),
            "claims": [
                answer.claims[0].model_dump(),
                {**answer.claims[0].model_dump(), "claim_id": "next", "evidence_ids": ["second"]},
            ],
        }
    )
    draft = FinalDraft(
        paragraphs=[
            {"text": "First.", "claim_ids": [answer.claims[0].claim_id]},
            {"text": "Second.", "claim_ids": ["next"]},
        ]
    )
    text = render(draft, answer, {"EV-source": first, "second": second})
    assert "First. [1]\n\nSecond. [1]" in text
    assert "s1 (characters 0–9); s2 (characters 10–20)" in text
