import asyncio

import pytest

from comtech.mcp.tools import ToolFailure, ToolService


@pytest.mark.parametrize(
    "tool,args,code",
    [
        ("get_employee", {"employee_id": "E9999"}, "NOT_FOUND"),
        ("get_employee", {"employee_id": "../employees"}, "INVALID_ARGUMENT"),
        ("get_employee", {"employee_id": 1043}, "INVALID_ARGUMENT"),
        ("get_employee", {}, "INVALID_ARGUMENT"),
        ("get_service", {"service_id": "merchantconnect", "role": "admin"}, "INVALID_ARGUMENT"),
        ("get_incident", {"incident_id": "INC-2026-038"}, "NOT_FOUND"),
        ("get_oncall", {"service_id": "merchantconnect", "at": "2026-09-15"}, "INVALID_ARGUMENT"),
        (
            "get_oncall",
            {"service_id": "merchantconnect", "at": "2026-02-30T10:00:00Z"},
            "INVALID_ARGUMENT",
        ),
        (
            "get_oncall",
            {"service_id": "merchantconnect", "at": "2026-09-16T08:00:00Z"},
            "OUT_OF_SNAPSHOT_RANGE",
        ),
        (
            "get_oncall",
            {"service_id": "merchantconnect", "at": "2026-09-15T07:59:59Z"},
            "OUT_OF_SNAPSHOT_RANGE",
        ),
        ("search_employees", {"query": " *? "}, "INVALID_ARGUMENT"),
        ("search_employees", {"query": " "}, "INVALID_ARGUMENT"),
        ("search_employees", {"query": "x" * 81}, "INVALID_ARGUMENT"),
        ("search_employees", {"query": "Alice", "team_id": "unknown"}, "NOT_FOUND"),
        ("list_open_incidents", {"service_id": "unknown"}, "NOT_FOUND"),
        ("unknown_tool", {}, "INVALID_ARGUMENT"),
    ],
)
async def test_tool_errors(snapshot, tool, args, code):
    result = await ToolService(snapshot).call(tool, args)
    assert result.is_error
    assert result.structured_content["error"]["code"] == code


async def test_handoff_and_response_isolation(snapshot):
    service = ToolService(snapshot)
    first = await service.call("get_oncall", {"service_id": "merchantconnect"})
    assert first.structured_content["payload"]["shift"]["employee_id"] == "E1043"
    next_shift = await service.call(
        "get_oncall", {"service_id": "merchantconnect", "at": "2026-09-15T20:00:00Z"}
    )
    assert next_shift.structured_content["payload"]["shift"]["employee_id"] == "E1051"
    offset = await service.call(
        "get_oncall", {"service_id": "merchantconnect", "at": "2026-09-16T01:30:00+05:30"}
    )
    assert offset.structured_content == next_shift.structured_content
    assert next_shift.structured_content["as_of"] == "2026-09-15T10:00:00Z"
    first.structured_content["payload"]["shift"]["employee_id"] = "corrupted-response"
    repeat = await service.call("get_oncall", {"service_id": "merchantconnect"})
    assert repeat.structured_content["payload"]["shift"]["employee_id"] == "E1043"


async def test_directory_and_empty_results(snapshot):
    service = ToolService(snapshot)
    result = await service.call("search_employees", {"query": "PAYMENTS PLATFORM"})
    assert {i["employee_id"] for i in result.structured_content["payload"]["items"]} == {
        "E1043",
        "E1044",
        "E1051",
    }
    truncated = await service.call("search_employees", {"query": "a"})
    payload = truncated.structured_content["payload"]
    assert payload["truncated"] and len(payload["items"]) == 10 and payload["total_matches"] > 10
    inactive = await service.call("get_employee", {"employee_id": "E0990"})
    assert inactive.structured_content["payload"]["active"] is False
    search = await service.call("search_employees", {"query": "Adrian"})
    assert search.structured_content["payload"]["items"] == []
    no_incidents = await service.call("list_open_incidents", {"service_id": "notifyhub"})
    assert not no_incidents.is_error and no_incidents.structured_content["payload"]["items"] == []


async def test_delay_timeout_unavailable_and_cancellation(snapshot):
    started, release = asyncio.Event(), asyncio.Event()

    async def controlled_delay(name, args):
        if name == "get_employee":
            started.set()
            await release.wait()
        if name == "get_incident":
            raise ToolFailure("UNAVAILABLE", "Injected unavailable lookup.")

    service = ToolService(snapshot, before_call=controlled_delay, timeout_seconds=0.5)
    slow = asyncio.create_task(service.call("get_employee", {"employee_id": "E1043"}))
    await started.wait()
    fast = await service.call("get_service", {"service_id": "payflow"})
    assert not fast.is_error and not slow.done()
    timed_out = await slow
    assert timed_out.structured_content["error"]["code"] == "TIMEOUT"
    unavailable = await service.call("get_incident", {"incident_id": "INC-LIVE-1042"})
    assert unavailable.structured_content["error"]["code"] == "UNAVAILABLE"
    started.clear()
    cancelled = asyncio.create_task(service.call("get_employee", {"employee_id": "E1043"}))
    await started.wait()
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    assert snapshot.get("employees", "E1043").name == "Alice Chen"
