import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import Decision, Limits
from comtech.agents.graph import build_enterprise_graph
from comtech.db import database
from comtech.research import accounting
from comtech.research.background import BackgroundGraph
from comtech.research.control import Control
from comtech.research.delivery import Delivery
from comtech.research.ledger import AccountingError, RunClosed
from comtech.research.queue import TaskQueue
from comtech.research.registry import JobRegistry
from comtech.research.scheduler import Scheduler
from tests.agents.helpers import FakeModel, FakeTools
from tests.test_integration import collect, server
from tests.test_integration import settings as settings

from .helpers import accounting_context, graph_config
from .test_background import configure
from .test_scheduler import eventually

pytestmark = pytest.mark.integration


async def test_cached_call_reuses_committed_output_and_original_budget(research_pool):
    ctx, _ = await accounting_context(research_pool)
    model = FakeModel()
    payload = {"task": {"task_id": "synthetic"}, "cycle": 0}
    with accounting.bind(ctx):
        first = await accounting.generate(model, "decision", payload, Decision, 1000)
        second = await accounting.generate(model, "decision", payload, Decision, 1000)
    assert first == second and len(model.calls) == 1
    assert (await ctx.ledger.counters(ctx.lease.objective_id))["model_requests"]["used"] == 1


async def test_restart_reuses_committed_call_without_a_fresh_allowance(research_pool):
    ctx, run = await accounting_context(research_pool)
    model = FakeModel()
    payload = {"task": {"task_id": "synthetic"}, "cycle": 0}
    with accounting.bind(ctx):
        await accounting.generate(model, "decision", payload, Decision, 1000)
    objective = await JobRegistry(research_pool).objective(run["id"])
    before = await ctx.ledger.counters(ctx.lease.objective_id)
    await Control(research_pool, Delivery(research_pool)).recover(objective["pinned_versions"])
    claim = await TaskQueue(research_pool).claim(uuid4(), ["supervisor"])
    assert claim.lease.fence == 2
    fresh = accounting.Accounting(ctx.ledger, claim.lease, accounting.Resources())
    with accounting.bind(fresh):
        await accounting.generate(model, "decision", payload, Decision, 1000)
    assert len(model.calls) == 1
    assert await fresh.ledger.counters(claim.lease.objective_id) == before
    recovered = await JobRegistry(research_pool).objective(run["id"])
    assert recovered["deadline"] == objective["deadline"]
    with pytest.raises(RunClosed):
        await fresh.ledger.check(ctx.lease)


async def test_unknown_inflight_outcome_terminates_without_retry_or_refund(research_pool):
    ctx, run = await accounting_context(research_pool)
    reservation = await ctx.ledger.reserve(ctx.lease, "uncertain-call", {"model_tokens": 500})
    await ctx.ledger.start(ctx.lease, reservation)
    control = Control(research_pool, Delivery(research_pool))
    await control.recover({})
    assert await TaskQueue(research_pool).claim(uuid4(), ["supervisor"]) is None
    async with research_pool.connection() as conn:
        row = await (
            await conn.execute("SELECT * FROM app_runs WHERE id=%s", (run["id"],))
        ).fetchone()
        assert (
            row["status"] == "failed" and row["terminal_reason"] == "uncertain_external_completion"
        )
    assert (await ctx.ledger.counters(ctx.lease.objective_id))["model_tokens"]["reserved"] == 500


async def test_cancel_repeated_or_after_completion_cannot_restart_work(settings, monkeypatch):
    tools = configure(settings, monkeypatch)
    tools.delay = 1
    async with server(settings) as client:
        run = (
            await client.post(
                "/api/runs",
                json={
                    "message": "Cancel me",
                    "execution_mode": "background",
                    "idempotency_key": "cancel-me",
                },
            )
        ).json()
        path = f"/api/runs/{run['run_id']}"
        async with asyncio.timeout(5):
            await tools.entered.wait()
        first = await client.post(path + "/cancel")
        second = await client.post(path + "/cancel")
        assert first.json()["status"] == second.json()["status"] == "cancelled"
        _, events = await collect(client, "GET", path + "/events?follow=true")
        assert events[-1][1]["code"] == "CANCELLED"
        assert not any(e["type"].startswith("TEXT_MESSAGE") for _, e in events)
        assert (await client.get(path + "/result")).status_code == 409
        assert (
            await client.post(path + "/resume", json={"checkpoint_id": "old"})
        ).status_code == 409


async def test_completed_checkpoint_publishes_after_restart_without_model_calls(research_pool):
    ctx, run = await accounting_context(research_pool)
    saver = AsyncPostgresSaver(research_pool)
    await saver.setup()
    model = FakeModel()
    graph = build_enterprise_graph(model, FakeTools(), TokenCounter(), Limits(), saver)
    with accounting.bind(ctx):
        await graph.ainvoke({"messages": [HumanMessage(content="Owner?")]}, graph_config(ctx, run))
    calls = len(model.calls)
    delivery = Delivery(research_pool)
    control = Control(research_pool, delivery)
    await control.recover({})
    queue = TaskQueue(research_pool, terminal_commit=delivery.terminal_locked)

    async def completed():
        async with research_pool.connection() as conn:
            row = await (
                await conn.execute("SELECT status FROM app_runs WHERE id=%s", (run["id"],))
            ).fetchone()
            return row["status"] == "completed"

    async with Scheduler(
        research_pool, {"supervisor": BackgroundGraph(graph, delivery, {})}, queue=queue
    ):
        await eventually(completed)
    assert len(model.calls) == calls


async def test_recorded_output_reconciles_cost_if_process_stopped_before_settlement(
    research_pool, monkeypatch
):
    ctx, _ = await accounting_context(research_pool)
    original = ctx.ledger.settle

    async def fail(*args, **kwargs):
        raise AccountingError("simulated persistence outage")

    monkeypatch.setattr(ctx.ledger, "settle", fail)
    model, payload = FakeModel(), {"task": {"task_id": "synthetic"}, "cycle": 0}
    with accounting.bind(ctx), pytest.raises(AccountingError):
        await accounting.generate(model, "decision", payload, Decision, 1000)
    monkeypatch.setattr(ctx.ledger, "settle", original)
    await Control(research_pool, Delivery(research_pool)).recover({})
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["model_tokens"]["reserved"] == 0 and counts["model_tokens"]["used"] == 30
    assert counts["model_requests"]["used"] == 1


async def test_pending_graph_resumes_existing_worker_results(research_pool):
    ctx, run = await accounting_context(research_pool)
    saver = AsyncPostgresSaver(research_pool)
    await saver.setup()
    model, tools = FakeModel(), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits(), saver)
    config = graph_config(ctx, run)
    with accounting.bind(ctx):
        await graph.ainvoke(
            {"messages": [HumanMessage(content="Owner?")]},
            config,
            interrupt_after=["knowledge_worker"],
        )
    snapshot = await graph.aget_state(config)
    assert snapshot.next and len(tools.calls) == 1
    original_result = snapshot.values["task_results"]
    delivery = Delivery(research_pool)
    await Control(research_pool, delivery).recover({})
    queue = TaskQueue(research_pool, terminal_commit=delivery.terminal_locked)

    async def completed():
        return (await queue.get(ctx.lease.task_id))["state"] == "completed"

    async with Scheduler(
        research_pool, {"supervisor": BackgroundGraph(graph, delivery, {})}, queue=queue
    ):
        await eventually(completed)
    assert len(tools.calls) == 1
    assert (await graph.aget_state(config)).values["task_results"] == original_result


async def test_restart_after_tool_receipt_before_worker_checkpoint(research_pool, monkeypatch):
    ctx, run = await accounting_context(research_pool)
    saver = AsyncPostgresSaver(research_pool)
    await saver.setup()
    model, tools = FakeModel(), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits(), saver)
    config = graph_config(ctx, run)
    recorded, never = asyncio.Event(), asyncio.Event()
    original = accounting.data_call

    async def pause_after_receipt(*args, **kwargs):
        result = await original(*args, **kwargs)
        recorded.set()
        await never.wait()
        return result

    monkeypatch.setattr(accounting, "data_call", pause_after_receipt)
    with accounting.bind(ctx):
        work = asyncio.create_task(
            graph.ainvoke({"messages": [HumanMessage(content="Owner?")]}, config)
        )
        await asyncio.wait_for(recorded.wait(), 5)
        work.cancel()
        with pytest.raises(asyncio.CancelledError):
            await work
    monkeypatch.setattr(accounting, "data_call", original)
    delivery = Delivery(research_pool)
    await Control(research_pool, delivery).recover({})
    queue = TaskQueue(research_pool, terminal_commit=delivery.terminal_locked)

    async def completed():
        return (await queue.get(ctx.lease.task_id))["state"] == "completed"

    async with Scheduler(
        research_pool, {"supervisor": BackgroundGraph(graph, delivery, {})}, queue=queue
    ):
        await eventually(completed)
    assert len(tools.calls) == 1
    assert (await delivery.ledger.counters(ctx.lease.objective_id))["data_requests"]["used"] == 1


async def test_expiry_and_changed_source_versions_do_not_reset_on_recovery(research_pool):
    for reason in ("deadline", "source_versions_unavailable"):
        ctx, run = await accounting_context(research_pool)
        if reason == "deadline":
            async with research_pool.connection() as conn:
                await conn.execute(
                    """UPDATE research_objectives SET created_at=now()-interval '3 seconds',
                    exploration_deadline=now()-interval '2 seconds',
                    deadline=now()-interval '1 second'
                    WHERE id=%s""",
                    (ctx.lease.objective_id,),
                )
        await Control(research_pool, Delivery(research_pool)).recover({"changed": "snapshot"})
        async with research_pool.connection() as conn:
            row = await (
                await conn.execute("SELECT * FROM app_runs WHERE id=%s", (run["id"],))
            ).fetchone()
            assert row["status"] == "failed" and row["terminal_reason"] == reason


async def test_api_restart_before_publication_reuses_calls_and_publishes_once(
    settings, monkeypatch
):
    configure(settings, monkeypatch)
    model, tools = FakeModel(), FakeTools()
    paused, never = asyncio.Event(), asyncio.Event()
    pause = True

    class PauseFinal:
        def __init__(self, graph):
            self.graph = graph

        def __getattr__(self, name):
            return getattr(self.graph, name)

        async def astream(self, *args, **kwargs):
            async for part in self.graph.astream(*args, **kwargs):
                if pause and part["type"] == "updates" and "final_answer" in part["data"]:
                    paused.set()
                    await never.wait()
                yield part

    @asynccontextmanager
    async def runtime(cfg, checkpointer):
        yield PauseFinal(
            build_enterprise_graph(model, tools, TokenCounter(), Limits(), checkpointer)
        )

    monkeypatch.setattr("comtech.agents.runtime.enterprise_runtime", runtime)
    async with server(settings) as client:
        response = await client.post(
            "/api/runs",
            json={
                "message": "Who owns the service?",
                "execution_mode": "background",
                "idempotency_key": "restart-publication",
            },
        )
        assert response.status_code == 202
        run = response.json()
        await asyncio.wait_for(paused.wait(), 5)
        async with database(settings.require_database()) as pool:
            snapshot = await AsyncPostgresSaver(pool).aget_tuple(
                {"configurable": {"thread_id": run["thread_id"]}}
            )
        resume_path = f"/api/runs/{run['run_id']}/resume"
        for _ in range(2):
            resumed = await client.post(
                resume_path,
                json={"checkpoint_id": snapshot.config["configurable"]["checkpoint_id"]},
            )
            assert resumed.status_code == 202 and resumed.json()["run_id"] == run["run_id"]
        assert (
            await client.post(resume_path, json={"checkpoint_id": str(uuid4())})
        ).status_code == 409
    calls = len(model.calls)
    async with database(settings.require_database()) as pool:
        objective = await JobRegistry(pool).objective(run["run_id"])
        before = await Delivery(pool).ledger.counters(objective["id"])
    pause = False
    async with server(settings) as client:
        _, events = await collect(client, "GET", run["events_url"])
        assert events[-1][1]["type"] == "RUN_FINISHED"
        assert sum(e["type"] == "TEXT_MESSAGE_CONTENT" for _, e in events) == 1
        path = f"/api/runs/{run['run_id']}"
        assert (await client.post(path + "/cancel")).json()["status"] == "completed"
    async with database(settings.require_database()) as pool:
        recovered = await JobRegistry(pool).objective(run["run_id"])
        assert recovered["id"] == objective["id"]
        assert recovered["deadline"] == objective["deadline"]
        after = await Delivery(pool).ledger.counters(objective["id"])
        for metric, prior in before.items():
            for field in ("ceiling", "used", "reserved"):
                assert after[metric][field] == prior[field]
            assert after[metric]["protected"] == 0  # Completion releases unused holds.
    assert len(model.calls) == calls and len(tools.calls) == 1
