import asyncio
from dataclasses import replace
from typing import TypedDict
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph

from comtech.research.accounting import CURRENT, source_call
from comtech.research.ledger import AccountingError, BudgetExhausted, RunClosed
from comtech.research.queue import TaskQueue
from comtech.research.registry import JobRegistry
from comtech.research.scheduler import Outcome, Scheduler

from .test_registry import submission

pytestmark = pytest.mark.integration


async def root(pool, **limits):
    run, _ = await JobRegistry(pool).submit(**submission())
    queue = TaskQueue(pool, **limits)
    claim = await queue.claim(uuid4(), ["supervisor"])
    assert claim.objective["run_id"] == run["id"]
    return queue, claim


async def test_claim_race_admission_dedupe_and_budget_rollback(research_pool):
    await JobRegistry(research_pool).submit(**submission())
    queue = TaskQueue(research_pool)
    claims = await asyncio.gather(*(queue.claim(uuid4(), ["supervisor"]) for _ in range(8)))
    assert sum(c is not None for c in claims) == 1
    claim = next(c for c in claims if c)
    tasks = await asyncio.gather(
        *(
            queue.enqueue(
                claim.lease,
                "same-analysis",
                "research",
                {"question": "synthetic"},
                {"model_tokens": 100},
            )
            for _ in range(6)
        )
    )
    assert len({t["id"] for t in tasks}) == 1
    with pytest.raises(AccountingError, match="different work"):
        await queue.enqueue(claim.lease, "same-analysis", "research", {}, {"model_tokens": 100})
    with pytest.raises(BudgetExhausted):
        await queue.enqueue(claim.lease, "oversized", "research", {}, {"model_tokens": 250_000})
    counts = await queue.ledger.counters(claim.lease.objective_id)
    assert counts["research_tasks"]["used"] == 1
    assert counts["specialist_calls"]["used"] == 1
    async with research_pool.connection() as conn:
        assert (await (await conn.execute("SELECT count(*) AS n FROM research_tasks")).fetchone())[
            "n"
        ] == 2


async def test_wait_releases_slot_early_result_resumes_and_all_failures_wake(research_pool):
    queue, claim = await root(research_pool, per_run=1)
    children = [
        await queue.enqueue(claim.lease, f"child-{i}", "research", {}, {}) for i in range(2)
    ]
    deps = [t["id"] for t in children]
    suspended = await queue.transition(
        claim.lease, state="waiting_children", dependencies=deps, continuation={"step": "assess"}
    )
    assert (
        await queue.transition(
            claim.lease,
            state="waiting_children",
            dependencies=deps,
            continuation={"step": "assess"},
        )
        == suspended
    )
    assert (await queue.get(claim.lease.task_id))["lease_owner"] is None
    first = await queue.claim(uuid4(), ["research"])
    assert first and await queue.claim(uuid4(), ["research"]) is None
    await queue.transition(first.lease, state="failed", reason="SyntheticFailure")
    resumed = await queue.claim(uuid4(), ["supervisor"])
    assert resumed.lease.fence == 2 and resumed.task["continuation"] == {"step": "assess"}
    assert len(resumed.dependencies) == 1 and resumed.dependencies[0]["state"] == "failed"
    with pytest.raises(RunClosed):
        await queue.heartbeat(claim.lease)
    with pytest.raises(AccountingError, match="cannot be changed"):
        await queue.transition(claim.lease, state="completed", result={"forged": True})
    await queue.transition(resumed.lease, state="waiting_children", dependencies=deps)
    assert (await queue.get(claim.lease.task_id))["state"] == "waiting_children"
    second = await queue.claim(uuid4(), ["research"])
    await queue.transition(second.lease, state="cancelled", reason="unavailable")
    last = await queue.claim(uuid4(), ["supervisor"])
    assert {d["state"] for d in last.dependencies} == {"failed", "cancelled"}
    await queue.transition(last.lease, state="completed", result={"supported_partial": True})
    assert await queue.claim(uuid4(), ["supervisor", "research"]) is None


async def test_dependency_cycles_and_foreign_objectives_are_rejected(research_pool):
    queue, claim = await root(research_pool, per_run=3)
    a = await queue.enqueue(claim.lease, "a", "research", {}, {})
    b = await queue.enqueue(claim.lease, "b", "research", {}, {})
    ca = await queue.claim(uuid4(), ["research"])
    cb = await queue.claim(uuid4(), ["research"])
    assert {ca.task["id"], cb.task["id"]} == {a["id"], b["id"]}
    await queue.transition(ca.lease, state="waiting_children", dependencies=[cb.task["id"]])
    for invalid in (cb.task["id"], ca.task["id"], claim.task["id"], uuid4()):
        with pytest.raises(AccountingError):
            await queue.transition(cb.lease, state="waiting_children", dependencies=[invalid])
    # A failed dependency transaction must not consume the attempt or change its task.
    assert (await queue.get(cb.task["id"]))["state"] == "running"


async def test_terminal_commit_is_immutable_and_uncertain_usage_keeps_call_reservation(
    research_pool,
):
    queue, claim = await root(research_pool)
    child = await queue.enqueue(claim.lease, "worker", "research", {}, {"model_tokens": 100})
    task = await queue.claim(uuid4(), ["research"])
    call = await queue.ledger.reserve(
        task.lease,
        "call",
        {"model_tokens": 50, "model_requests": 1},
        scope=child["scope_key"],
        phase="finalization",
    )
    await queue.ledger.start(task.lease, call)
    with pytest.raises(AccountingError, match="in flight"):
        await queue.transition(task.lease, state="completed", result={"evidence_ref": "synthetic"})
    await queue.ledger.settle(call, {"model_requests": 1})
    results = await asyncio.gather(
        *(
            queue.transition(task.lease, state="completed", result={"evidence_ref": "synthetic"})
            for _ in range(2)
        )
    )
    assert results[0] == results[1]
    with pytest.raises(AccountingError):
        await queue.transition(
            replace(task.lease, owner=uuid4()),
            state="completed",
            result={"evidence_ref": "synthetic"},
        )
    counts = await queue.ledger.counters(task.lease.objective_id)
    assert counts["model_tokens"]["reserved"] == 50
    assert counts["model_tokens"]["protected"] == 24000
    await queue.ledger.settle(call, {"model_tokens": 20})
    counts = await queue.ledger.counters(task.lease.objective_id)
    assert counts["model_tokens"]["used"] == 20
    assert counts["model_tokens"]["reserved"] == 0
    assert counts["model_tokens"]["protected"] == 24000


async def test_claim_caps_deadlines_and_no_automatic_expired_retry(research_pool):
    queue, one = await root(research_pool, max_runs=1, per_run=1, lease_seconds=1)
    await JobRegistry(research_pool).submit(**submission())
    assert await queue.claim(uuid4(), ["supervisor"]) is None
    await queue.heartbeat(one.lease)
    async with research_pool.connection() as conn:
        await conn.execute(
            "UPDATE research_tasks SET lease_expires_at=now()-interval '1 second' WHERE id=%s",
            (one.task["id"],),
        )
    with pytest.raises(RunClosed):
        await queue.heartbeat(one.lease)
    assert await queue.claim(uuid4(), ["supervisor"]) is None
    # No lease is silently stolen before R2.5 reconciles possible external work.
    assert (await queue.get(one.task["id"]))["fence"] == 1


async def eventually(predicate):
    async with asyncio.timeout(10):
        while not await predicate():  # noqa: ASYNC110 - poll durable state, not process-local events
            await asyncio.sleep(0.02)


async def test_supervised_scheduler_runs_waiting_continuation_with_shared_accounting(research_pool):
    registry = JobRegistry(research_pool)
    run, _ = await registry.submit(**submission())
    contexts, stages = [], []
    queue = TaskQueue(research_pool, per_run=1, lease_seconds=0.3)
    root_id = None

    async def supervisor(claim):
        nonlocal root_id
        root_id = claim.task["id"]
        contexts.append(CURRENT.get())
        stages.append(claim.task["kind"])
        if not claim.task["continuation"]:
            child = await queue.enqueue(claim.lease, "fake-specialist", "research", {}, {})
            return Outcome(
                state="waiting_children",
                dependencies=(child["id"],),
                continuation={"awaiting": True},
            )
        assert claim.dependencies[0]["result"] == {"claim_ref": "synthetic-supported-claim"}
        return Outcome(result={"approved_result_ref": "synthetic-result"})

    async def specialist(claim):
        contexts.append(CURRENT.get())
        stages.append(claim.task["kind"])
        await source_call(lambda: asyncio.sleep(0.4))  # Heartbeat outlives the first lease.
        return Outcome(result={"claim_ref": "synthetic-supported-claim"})

    async def completed():
        return root_id is not None and (await queue.get(root_id))["state"] == "completed"

    async with Scheduler(
        research_pool,
        {"supervisor": supervisor, "research": specialist},
        queue=queue,
        poll_seconds=0.01,
    ) as scheduler:
        await eventually(completed)
        scheduler.check_health()
        assert stages == ["supervisor", "research", "supervisor"]
        assert all(c.resources is scheduler.resources for c in contexts)
        assert len({c.lease.attempt_id for c in contexts}) == 3
    objective = await registry.objective(run["id"])
    assert (await queue.ledger.counters(objective["id"]))["source_requests"]["used"] == 1
    async with research_pool.connection() as conn:
        # R2.4 alone will publish reviewed final answers and terminate the user run.
        events = await (await conn.execute("SELECT count(*) AS n FROM app_run_events")).fetchone()
        assert events["n"] == 0


async def test_langgraph_checkpoint_continues_under_new_attempt_without_repeating_node(
    research_pool,
):
    await JobRegistry(research_pool).submit(**submission())
    queue = TaskQueue(research_pool, per_run=1)
    saver = AsyncPostgresSaver(research_pool)
    await saver.setup()
    visits = []
    finished = asyncio.Event()

    class State(TypedDict):
        child: str
        answer_ref: str

    async def delegate(state):
        visits.append("delegate")
        child = await queue.enqueue(CURRENT.get().lease, "scripted-child", "research", {}, {})
        return {"child": str(child["id"])}

    async def resume(state):
        visits.append("resume")
        child = await queue.get(state["child"])
        assert child["state"] == "completed"
        return {"answer_ref": child["result"]["ref"]}

    builder = StateGraph(State)
    builder.add_node("delegate", delegate)
    builder.add_node("resume", resume)
    builder.add_edge(START, "delegate")
    builder.add_edge("delegate", "resume")
    builder.add_edge("resume", END)
    graph = builder.compile(checkpointer=saver, interrupt_before=["resume"])

    async def supervisor(claim):
        config = {"configurable": {"thread_id": str(claim.objective["thread_id"])}}
        if not claim.task["continuation"]:
            output = await graph.ainvoke({"child": "", "answer_ref": ""}, config)
            checkpoint = await graph.aget_state(config)
            return Outcome(
                state="waiting_children",
                dependencies=(output["child"],),
                continuation={"checkpoint_id": checkpoint.config["configurable"]["checkpoint_id"]},
            )
        config["configurable"].update(claim.task["continuation"])
        output = await graph.ainvoke(None, config)
        finished.set()
        return Outcome(result={"ref": output["answer_ref"]})

    async def child(claim):
        return Outcome(result={"ref": "synthetic-evidence"})

    async with Scheduler(
        research_pool, {"supervisor": supervisor, "research": child}, queue=queue, poll_seconds=0.01
    ):
        async with asyncio.timeout(10):
            await finished.wait()

        async def committed():
            async with research_pool.connection() as conn:
                row = await (
                    await conn.execute(
                        "SELECT state,result FROM research_tasks WHERE kind='supervisor'"
                    )
                ).fetchone()
                return row["state"] == "completed" and row["result"] == {
                    "ref": "synthetic-evidence"
                }

        await eventually(committed)
    assert visits == ["delegate", "resume"]


async def test_shutdown_retains_resources_until_detached_io_finishes(research_pool):
    await JobRegistry(research_pool).submit(**submission())
    entered, returned, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    nested_entered, nested_release = asyncio.Event(), asyncio.Event()
    attempt = None

    async def operation():
        entered.set()
        await release.wait()

        # A timed-out logical call can still reach another source while draining.
        async def nested():
            nested_entered.set()
            await nested_release.wait()

        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.02):
                await source_call(nested)

    async def handler(claim):
        nonlocal attempt
        attempt = claim.lease
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                await source_call(operation)
        returned.set()
        return Outcome(result={"must_not_commit_during_shutdown": True})

    scheduler = await Scheduler(
        research_pool, {"supervisor": handler}, poll_seconds=0.01
    ).__aenter__()
    closing = None
    try:
        async with asyncio.timeout(10):
            await entered.wait()
            await returned.wait()
        closing = asyncio.create_task(scheduler.__aexit__())
        await asyncio.sleep(0.03)
        assert not closing.done() and scheduler.resources.inflight
        release.set()
        async with asyncio.timeout(5):
            await nested_entered.wait()
        await asyncio.sleep(0.04)
        assert not closing.done() and scheduler.resources.inflight
        nested_release.set()
        await closing
        row = await scheduler.queue.get(attempt.task_id)
        assert row["state"] == "running" and row["result"] is None
        counts = await scheduler.queue.ledger.counters(attempt.objective_id)
        assert counts["source_requests"]["used"] == 2
        assert not scheduler.resources.inflight
    finally:
        release.set()
        nested_release.set()
        if closing:
            await closing
        else:
            await scheduler.__aexit__()


async def test_handler_failure_is_control_state_without_invented_result(research_pool):
    await JobRegistry(research_pool).submit(**submission())
    task_id = None

    async def handler(claim):
        nonlocal task_id
        task_id = claim.task["id"]
        raise ValueError("Do not publish raw exception content")

    async with Scheduler(research_pool, {"supervisor": handler}, poll_seconds=0.01) as scheduler:

        async def failed():
            return task_id is not None and (await scheduler.queue.get(task_id))["state"] == "failed"

        await eventually(failed)
        row = await scheduler.queue.get(task_id)
        assert row["result"] is None and row["termination_reason"] == "ValueError"
        scheduler.check_health()
