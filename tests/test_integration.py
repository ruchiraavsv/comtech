"""Real HTTP streaming against isolated Postgres; no paid provider calls."""

import asyncio
import os
import socket
from contextlib import asynccontextmanager, contextmanager
from uuid import uuid4

import httpx
import pytest
import uvicorn
from httpx_sse import aconnect_sse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from comtech.api.app import create_app
from comtech.db import database, migrate
from comtech.settings import Settings

pytestmark = [pytest.mark.integration]


class TestServer(uvicorn.Server):
    # Multiple server lifetimes share the pytest process; do not install process
    # signal handlers (SSE's shutdown watcher otherwise observes an old server).
    __test__ = False

    @contextmanager
    def capture_signals(self):
        yield


@pytest.fixture(params=["off", "phoenix"])
async def settings(request):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to an isolated test database")
    cfg = Settings(
        _env_file=None,
        database_url=url,
        app_env="test",
        langsmith_tracing=False,
        observability_mode=request.param,
        phoenix_trace_endpoint="http://127.0.0.1:1/v1/traces",
        mock_delay_seconds=0.15,
    )
    async with database(url) as pool:
        await migrate(pool)
        await AsyncPostgresSaver(pool).setup()
    return cfg


@asynccontextmanager
async def server(settings):
    async with http_server(create_app(settings)) as client:
        yield client


@asynccontextmanager
async def http_server(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    instance = TestServer(uvicorn.Config(app, log_config=None, access_log=False, lifespan="on"))
    task = asyncio.create_task(instance.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(15):
            while not instance.started:
                if task.done():
                    await task
                    raise RuntimeError("Server exited before startup")
                await asyncio.sleep(0.02)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as client:
            yield client
    finally:
        instance.should_exit = True
        await task
        sock.close()


async def collect(client, method, path, **kwargs):
    async with aconnect_sse(client, method, path, **kwargs) as source:
        source.response.raise_for_status()
        headers = source.response.headers
        events = [(item.id, item.json()) async for item in source.aiter_sse() if item.data]
    return headers, events


async def test_enterprise_api_stream_followup_and_replay(settings, monkeypatch):
    from comtech.agents.budget import TokenCounter
    from comtech.agents.contracts import Limits
    from comtech.agents.graph import build_enterprise_graph
    from tests.agents.helpers import FakeModel, FakeTools

    @asynccontextmanager
    async def fake_runtime(cfg, checkpointer):
        yield build_enterprise_graph(
            FakeModel(), FakeTools(), TokenCounter(), Limits(), checkpointer
        )

    monkeypatch.setattr("comtech.agents.runtime.enterprise_runtime", fake_runtime)
    settings.agent_mode = "enterprise"
    thread = str(uuid4())
    async with server(settings) as client:
        health = (await client.get("/health/ready")).json()
        assert health["mode"] == "enterprise"
        headers, events = await collect(
            client,
            "POST",
            "/api/runs",
            json={"thread_id": thread, "message": "Who owns the service?"},
        )
        assert events[-1][1]["type"] == "RUN_FINISHED"
        text = [e for _, e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        assert len(text) == 1 and "[1]" in text[0]["delta"]
        stored = (await client.get(f"/api/runs/{headers['x-run-id']}")).json()
        assert stored["graph_run_id"] == headers["x-run-id"]
        assert stored["graph_version"] == 2
        assert any(e.get("name") == "agent.activity" for _, e in events)
        _, replay = await collect(client, "GET", f"/api/runs/{headers['x-run-id']}/events")
        assert replay == events
        _, followup = await collect(
            client, "POST", "/api/runs", json={"thread_id": thread, "message": "And now?"}
        )
        assert followup[-1][1]["type"] == "RUN_FINISHED"


async def test_live_stream_concurrency_persistence_and_cursor_replay(settings):
    thread = str(uuid4())
    async with server(settings) as client:
        async with aconnect_sse(
            client, "POST", "/api/runs", json={"thread_id": thread, "message": "hello"}
        ) as source:
            source.response.raise_for_status()
            run_id = source.response.headers["x-run-id"]
            original = []
            async for item in source.aiter_sse():
                if not item.data:
                    continue
                original.append((item.id, item.json()))
                if item.json()["type"] == "CUSTOM" and len(original) == 3:
                    state = (await client.get(f"/api/runs/{run_id}")).json()
                    assert state["status"] == "running"  # Event arrived before completion.
                    assert (await client.get("/health/live")).status_code == 200
                    conflict = await client.post(
                        "/api/runs", json={"thread_id": thread, "message": "overlap"}
                    )
                    assert conflict.status_code == 409
        assert original[-1][1]["type"] == "RUN_FINISHED"
        stored = (await client.get(f"/api/runs/{run_id}")).json()
        if settings.tracing_mode == "phoenix":
            assert len(stored["otel_trace_id"]) == 32
        else:
            assert stored["otel_trace_id"] is None
        _, second = await collect(
            client, "POST", "/api/runs", json={"thread_id": thread, "message": "again"}
        )
        assert any("turn 2" in event.get("delta", "") for _, event in second)
    # New application/pool/graph instance, same durable database.
    async with server(settings) as client:
        _, replay = await collect(client, "GET", f"/api/runs/{run_id}/events")
        assert replay == original
        _, suffix = await collect(
            client, "GET", f"/api/runs/{run_id}/events", headers={"Last-Event-ID": original[2][0]}
        )
        assert suffix == original[3:]
        runs = (await client.get(f"/api/threads/{thread}/runs")).json()
        assert len(runs) == 2  # Replay did not create execution.
        history = (await client.get(f"/api/threads/{thread}/checkpoints")).json()
        assert "turn 2" in history[0]["messages"][-1]["content"]


async def test_failure_timeout_and_disconnect_resume(settings):
    async with server(settings) as client:
        headers, events = await collect(client, "POST", "/api/runs", json={"message": "/fail"})
        assert events[-1][1]["type"] == "RUN_ERROR"
        assert (await client.get(f"/api/runs/{headers['x-run-id']}")).json()["status"] == "failed"
        thread = str(uuid4())
        async with aconnect_sse(
            client, "POST", "/api/runs", json={"thread_id": thread, "message": "disconnect"}
        ) as source:
            run_id = source.response.headers["x-run-id"]
            async for event in source.aiter_sse():
                if event.data and event.json()["type"] == "CUSTOM":
                    break
        for _ in range(100):
            state = (await client.get(f"/api/runs/{run_id}")).json()
            if state["status"] != "running":
                break
            await asyncio.sleep(0.02)
        assert state["status"] == "interrupted"
    async with server(settings) as client:
        history = (await client.get(f"/api/threads/{thread}/checkpoints")).json()
        checkpoint = next(item for item in history if item["next"] == ["mock_node"])
        headers, events = await collect(
            client,
            "POST",
            f"/api/runs/{run_id}/resume",
            json={"checkpoint_id": checkpoint["checkpoint_id"]},
        )
        assert events[-1][1]["type"] == "RUN_FINISHED"
        assert headers["x-run-id"] != run_id
    settings.request_timeout_seconds = 0.05
    async with server(settings) as client:
        _, events = await collect(client, "POST", "/api/runs", json={"message": "timeout"})
        assert events[-1][1]["code"] == "TIMEOUT"


async def test_independent_conversations_run_concurrently(settings):
    async with server(settings) as client:
        async with aconnect_sse(client, "POST", "/api/runs", json={"message": "first"}) as first:
            first_events = first.aiter_sse()
            async for event in first_events:
                if event.data and event.json()["type"] == "CUSTOM":
                    break
            # A second conversation starts while the first remains active.
            async with aconnect_sse(
                client, "POST", "/api/runs", json={"message": "second"}
            ) as second:
                second.response.raise_for_status()
                assert (
                    first.response.headers["x-thread-id"] != second.response.headers["x-thread-id"]
                )
                assert (await client.get(f"/api/runs/{first.response.headers['x-run-id']}")).json()[
                    "status"
                ] == "running"
                async for event in second.aiter_sse():
                    if event.data and event.json()["type"] == "RUN_FINISHED":
                        break
            remaining = [event.json() async for event in first_events if event.data]
            assert remaining[-1]["type"] == "RUN_FINISHED"


async def test_database_background_admission_blocks_stream_and_legacy_resume(settings):
    from comtech.research.contracts import SourceScope
    from comtech.research.registry import JobRegistry

    thread = uuid4()
    async with database(settings.require_database()) as pool:
        run, _ = await JobRegistry(pool).submit(
            thread_id=thread,
            idempotency_key="private-test",
            message="Synthetic question",
            scope=SourceScope(
                scope_ref="test",
                sources=[],
                datasets={},
                fields={},
                capabilities=[],
                pinned_versions={},
            ),
            budget_profile={},
        )
    try:
        async with server(settings) as client:
            response = await client.post(
                "/api/runs",
                json={"thread_id": str(thread), "message": "Competing stream"},
            )
            assert response.status_code == 409
            response = await client.post(
                f"/api/runs/{run['id']}/resume",
                json={"checkpoint_id": "cannot-fork"},
            )
            assert response.status_code == 409
            runs = (await client.get(f"/api/threads/{thread}/runs")).json()
            assert len(runs) == 1 and runs[0]["status"] == "queued"
    finally:
        async with database(settings.require_database()) as pool, pool.connection() as conn:
            await conn.execute("UPDATE app_runs SET status='cancelled' WHERE id=%s", (run["id"],))
