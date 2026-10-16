import asyncio

import httpx
import pytest
from mcp import Client

from comtech.mcp.server import create_app
from comtech.mcp.settings import MCPSettings
from comtech.mcp.tools import TOOL_SPECS, ToolService

from .conftest import FIXTURES, serve


async def test_discovery_and_live_story_over_http(server_url):
    async with httpx.AsyncClient() as http:
        health = await http.get(server_url + "/health/ready")
        assert health.status_code == 200 and health.json()["snapshot_id"] == "DEMO-2026-09-15-A"
    async with Client(server_url + "/mcp") as client:
        listing = await client.list_tools()
        assert {t.name for t in listing.tools} == set(TOOL_SPECS)
        assert all(
            t.input_schema and t.output_schema and t.annotations.read_only_hint
            for t in listing.tools
        )
        result = await client.call_tool("list_open_incidents", {})
        assert len(result.structured_content["payload"]["items"]) == 3
        incident = (
            await client.call_tool("get_incident", {"incident_id": "INC-LIVE-1042"})
        ).structured_content["payload"]
        assert incident["confirmed_root_cause"] is None
        service = (
            await client.call_tool("get_service", {"service_id": incident["service_id"]})
        ).structured_content["payload"]
        assert service["owner_team"]["name"] == "Payments Platform Reliability"
        shift = (
            await client.call_tool("get_oncall", {"service_id": incident["service_id"]})
        ).structured_content["payload"]["shift"]
        employee = (
            await client.call_tool("get_employee", {"employee_id": shift["employee_id"]})
        ).structured_content["payload"]
        assert (
            employee["name"] == "Alice Chen" and employee["email"] == "alice.chen@northstar.example"
        )
        deployment = await client.call_tool(
            "get_current_deployment", {"service_id": "merchantconnect"}
        )
        assert deployment.structured_content["payload"]["version"] == "4.7.2"
        directory = await client.call_tool("search_employees", {"query": "alice"})
        assert directory.structured_content["payload"]["items"][0]["employee_id"] == "E1043"
        for arguments in ({}, {"employee_id": "E9999"}, {"employee_id": "bad"}):
            failed = await client.call_tool("get_employee", arguments)
            assert failed.is_error and "error" in failed.structured_content


async def test_fifty_concurrent_queries_from_ten_clients(server_url):
    count = 0
    connected = asyncio.Event()

    async def agent(number):
        nonlocal count
        async with Client(server_url + "/mcp") as client:
            count += 1
            if count == 10:
                connected.set()
            await connected.wait()
            service_id = "merchantconnect" if number % 2 else "payflow"
            at = "2026-09-15T10:00:00Z" if number < 5 else "2026-09-15T20:00:00Z"
            expected = {
                ("merchantconnect", True): "E1043",
                ("merchantconnect", False): "E1051",
                ("payflow", True): "E2050",
                ("payflow", False): "E2052",
            }[(service_id, number < 5)]
            results = await asyncio.gather(
                *(
                    client.call_tool("get_oncall", {"service_id": service_id, "at": at})
                    for _ in range(5)
                )
            )
            assert all(
                not r.is_error
                and r.structured_content["payload"]["shift"]["employee_id"] == expected
                for r in results
            )

    async with asyncio.timeout(30):
        await asyncio.gather(*(agent(number) for number in range(10)))


async def test_slow_connection_does_not_block_other_connection():
    entered, release = asyncio.Event(), asyncio.Event()

    async def block_one(name, args):
        if name == "get_employee":
            entered.set()
            await release.wait()

    def factory(snapshot, **kwargs):
        return ToolService(snapshot, before_call=block_one, **kwargs)

    app = create_app(MCPSettings(fixture_directory=FIXTURES), service_factory=factory)
    async with serve(app) as url, Client(url + "/mcp") as one, Client(url + "/mcp") as two:
        slow = asyncio.create_task(one.call_tool("get_employee", {"employee_id": "E1043"}))
        await entered.wait()
        try:
            fast = await asyncio.wait_for(
                two.call_tool("get_service", {"service_id": "payflow"}), 2
            )
            assert not fast.is_error and not slow.done()
        finally:
            release.set()
        assert not (await slow).is_error


async def test_http_host_origin_and_unknown_path(server_url):
    async with httpx.AsyncClient() as client:
        assert (await client.get(server_url + "/other")).status_code == 404
        host = await client.post(
            server_url + "/mcp", headers={"Host": "untrusted.example"}, json={}
        )
        assert host.status_code == 421
        origin = await client.post(
            server_url + "/mcp", headers={"Origin": "https://untrusted.example"}, json={}
        )
        assert origin.status_code == 403


async def test_invalid_snapshot_never_becomes_ready(tmp_path):
    app = create_app(MCPSettings(fixture_directory=tmp_path))
    with pytest.raises(FileNotFoundError):
        async with app.router.lifespan_context(app):
            pytest.fail("Invalid fixtures reached serving state")
    assert not app.state.ready


async def test_restart_preserves_results():
    responses = []
    for _ in range(2):
        app = create_app(MCPSettings(fixture_directory=FIXTURES))
        async with serve(app) as url, Client(url + "/mcp") as client:
            responses.append(
                (
                    await client.call_tool("get_incident", {"incident_id": "INC-LIVE-1042"})
                ).structured_content
            )
        assert not app.state.ready
    assert responses[0] == responses[1]
