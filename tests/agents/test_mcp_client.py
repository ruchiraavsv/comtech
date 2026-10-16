import json

from comtech.agents.budget import digest
from comtech.agents.contracts import ClaimDraft, KnowledgeWorkerDraftResult, Selection
from comtech.agents.evidence import materialize
from comtech.integrations.northstar import NorthstarClient
from tests.mcp.conftest import server_url as server_url


async def test_application_adapter_discovery_provenance_and_errors(server_url):
    client = NorthstarClient(server_url + "/mcp")
    await client.discover()
    for name, args in [
        ("search_employees", {"query": "Alice"}),
        ("get_employee", {"employee_id": "E1043"}),
        ("get_service", {"service_id": "merchantconnect"}),
        ("get_oncall", {"service_id": "merchantconnect"}),
        ("list_open_incidents", {}),
        ("get_incident", {"incident_id": "INC-LIVE-1042"}),
        ("get_current_deployment", {"service_id": "merchantconnect"}),
    ]:
        result = await client.call(name, args)
        assert not result.error
        assert result.observations[0].as_of == "2026-09-15T10:00:00Z"
        assert result.observations[0].source_ref.version == "DEMO-2026-09-15-A"
    failed = await client.call("get_employee", {"employee_id": "E9999"})
    assert failed.error.code == "NOT_FOUND" and not failed.observations
    horizon = await client.call(
        "get_oncall", {"service_id": "merchantconnect", "at": "2025-01-01T00:00:00Z"}
    )
    assert horizon.error.code == "OUT_OF_SNAPSHOT_RANGE"


async def test_empty_incident_query_keeps_verified_filter_through_evidence_selection(server_url):
    result = await NorthstarClient(server_url + "/mcp").call(
        "list_open_incidents", {"service_id": "notifyhub"}
    )
    observation = result.observations[0]
    content = json.loads(observation.content)
    assert content["items"] == []
    assert content["_query"] == {
        "tool": "list_open_incidents",
        "arguments": {"service_id": "notifyhub"},
    }
    assert observation.content_hash == digest(observation.content)
    draft = KnowledgeWorkerDraftResult(
        status="answered",
        claims=[
            ClaimDraft(
                claim_id="empty",
                statement="The snapshot query returned no open NotifyHub incidents.",
                support="direct",
                evidence=[Selection(observation_id=observation.observation_id)],
            )
        ],
        unresolved=[],
    )
    _, evidence = materialize(
        draft, {observation.observation_id: observation}, "run", "task", "completed", []
    )
    selected = next(iter(evidence.values()))
    assert selected.content == observation.content
    assert selected.content_hash == observation.content_hash
