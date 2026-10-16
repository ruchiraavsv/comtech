import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from httpx_sse import aconnect_sse

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import Limits
from comtech.agents.graph import build_enterprise_graph
from comtech.research.delivery import Delivery
from comtech.research.queue import TaskQueue
from tests.agents.helpers import FakeModel, FakeTools
from tests.test_integration import collect, server
from tests.test_integration import settings as settings

from .helpers import accounting_context

pytestmark = pytest.mark.integration


def configure(settings, monkeypatch, *, reject=False):
    tools = FakeTools(delay=0.2)
    model = FakeModel(reject=reject)

    @asynccontextmanager
    async def runtime(cfg, checkpointer):
        yield build_enterprise_graph(model, tools, TokenCounter(), Limits(), checkpointer)

    monkeypatch.setattr("comtech.agents.runtime.enterprise_runtime", runtime)
    settings.agent_mode = "enterprise"
    settings.background_enabled = True
    settings.request_timeout_seconds = 0.05
    return tools


async def test_background_duplicate_submission_disconnect_follow_and_final_result(
    settings, monkeypatch
):
    tools = configure(settings, monkeypatch)
    body = {
        "message": "Who owns the service?",
        "thread_id": str(uuid4()),
        "execution_mode": "background",
        "idempotency_key": "request-1",
    }
    async with server(settings) as client:
        responses = await asyncio.gather(*(client.post("/api/runs", json=body) for _ in range(4)))
        assert all(r.status_code == 202 for r in responses)
        assert len({r.json()["run_id"] for r in responses}) == 1
        run = responses[0].json()
        path = f"/api/runs/{run['run_id']}"
        assert (
            await client.post("/api/runs", json={**body, "message": "Different"})
        ).status_code == 409
        assert (
            await client.post("/api/runs", json={**body, "execution_mode": "stream"})
        ).status_code == 409
        async with aconnect_sse(client, "GET", run["events_url"]) as source:
            async for event in source.aiter_sse():
                if event.data:
                    cursor = event.id
                    break  # Browser disconnects while the graph continues.
        _, remaining = await collect(
            client, "GET", run["events_url"], headers={"Last-Event-ID": cursor}
        )
        assert remaining[-1][1]["type"] == "RUN_FINISHED"
        state = (await client.get(path)).json()
        assert state["status"] == "completed" and state["result_available"]
        result = (await client.get(run["result_url"])).json()
        assert "[1]" in result["answer"] and result["review_status"] == "approved"
        assert "result" not in state and "input" not in state
        _, all_events = await collect(client, "GET", path + "/events")
        assert len([e for _, e in all_events if e["type"] == "TEXT_MESSAGE_CONTENT"]) == 1
        assert [int(i.rsplit(":", 1)[1]) for i, _ in all_events] == list(
            range(1, len(all_events) + 1)
        )
        assert len(tools.calls) == 1
        assert (await client.post("/api/runs", json=body)).json()["run_id"] == run["run_id"]
        assert (
            await client.get(path + "/events", headers={"Last-Event-ID": f"{uuid4()}:1"})
        ).status_code == 400
    # Delivery after a new API instance cannot restart a completed task.
    async with server(settings) as client:
        assert (await client.get(run["result_url"])).json() == result
        _, replay = await collect(client, "GET", path + "/events?follow=true")
        assert replay == all_events and len(tools.calls) == 1


async def test_review_failure_publishes_control_error_without_answer(settings, monkeypatch):
    configure(settings, monkeypatch, reject=True)
    async with server(settings) as client:
        submitted = await client.post(
            "/api/runs",
            json={
                "message": "Synthetic review failure",
                "execution_mode": "background",
                "idempotency_key": "failure",
            },
        )
        run = submitted.json()
        _, events = await collect(client, "GET", run["events_url"])
        assert events[-1][1]["type"] == "RUN_ERROR"
        assert not any(e["type"].startswith("TEXT_MESSAGE") for _, e in events)
        assert (await client.get(f"/api/runs/{run['run_id']}")).json()["status"] == "failed"
        assert (await client.get(run["result_url"])).status_code == 409


async def test_background_flag_and_key_are_explicit(settings, monkeypatch):
    async with server(settings) as client:
        assert (
            await client.post(
                "/api/runs",
                json={
                    "message": "disabled",
                    "execution_mode": "background",
                    "idempotency_key": "a",
                },
            )
        ).status_code == 409
    configure(settings, monkeypatch)
    async with server(settings) as client:
        assert (
            await client.post(
                "/api/runs", json={"message": "no key", "execution_mode": "background"}
            )
        ).status_code == 422


async def test_publication_failure_rolls_back_task_answer_status_and_events(research_pool):
    from psycopg.errors import RaiseException

    ctx, run = await accounting_context(research_pool)
    delivery = Delivery(research_pool)
    queue = TaskQueue(research_pool, terminal_commit=delivery.terminal_locked)
    result = {"answer": "Scripted reviewed answer", "review_status": "approved"}
    async with research_pool.connection() as conn:
        await conn.execute("""CREATE FUNCTION reject_event() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'simulated storage failure'; END $$""")
        await conn.execute(
            "CREATE TRIGGER reject_event BEFORE INSERT ON app_run_events "
            "FOR EACH ROW EXECUTE FUNCTION reject_event()"
        )
    with pytest.raises(RaiseException):
        await queue.transition(ctx.lease, state="completed", result=result)
    assert (await queue.get(ctx.lease.task_id))["state"] == "running"
    async with research_pool.connection() as conn:
        row = await (
            await conn.execute("SELECT * FROM app_runs WHERE id=%s", (run["id"],))
        ).fetchone()
        assert row["result"] is None and row["event_sequence"] == 0
        assert row["status"] == "queued"
        await conn.execute("DROP TRIGGER reject_event ON app_run_events")
    for _ in range(2):
        await queue.transition(ctx.lease, state="completed", result=result)
    async with research_pool.connection() as conn:
        row = await (
            await conn.execute("SELECT * FROM app_runs WHERE id=%s", (run["id"],))
        ).fetchone()
        assert row["status"] == "completed" and row["event_sequence"] == 4
        assert row["result"] == result
