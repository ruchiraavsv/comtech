import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest

from comtech.research.budgets import BudgetProfile
from comtech.research.ledger import AccountingError, BudgetExhausted, RunClosed

from .helpers import accounting_context

pytestmark = pytest.mark.integration


def profile(tokens=1000, reserve=100):
    base = BudgetProfile()
    return {
        "limits": {**base.limits, "model_tokens": tokens},
        "final_reserve": {"model_tokens": reserve},
    }


async def test_race_last_reservation_and_finalization_reserve(research_pool):
    ctx, _ = await accounting_context(research_pool, profile())
    ledger, lease = ctx.ledger, ctx.lease
    results = await asyncio.gather(
        *(ledger.reserve(lease, str(i), {"model_tokens": 900}) for i in range(2)),
        return_exceptions=True,
    )
    assert sum(isinstance(r, BudgetExhausted) for r in results) == 1
    reserved = next(r for r in results if not isinstance(r, BaseException))
    final = await ledger.reserve(lease, "final", {"model_tokens": 100}, phase="finalization")
    await ledger.start(lease, final)
    await asyncio.gather(*(ledger.settle(final, {"model_tokens": 40}) for _ in range(2)))
    counts = await ledger.counters(lease.objective_id)
    assert (
        counts["model_tokens"]["used"],
        counts["model_tokens"]["reserved"],
        counts["model_tokens"]["protected"],
    ) == (40, 900, 60)
    await ledger.release(lease, reserved)
    with pytest.raises(AccountingError, match="undispatched"):
        await ledger.settle(reserved, {"model_tokens": 0})


async def test_partitioned_holds_are_idempotent_and_cannot_share_remaining_budget(research_pool):
    ctx, _ = await accounting_context(research_pool, profile())
    ledger, lease = ctx.ledger, ctx.lease
    await ledger.protect(lease, "child-a", {"model_tokens": 600})
    await ledger.protect(lease, "child-a", {"model_tokens": 600})
    with pytest.raises(BudgetExhausted):
        await ledger.protect(
            lease, "child-b", {"model_tokens": 600}, charge={"specialist_calls": 1}
        )
    assert (await ledger.counters(lease.objective_id))["specialist_calls"]["used"] == 0
    with pytest.raises(AccountingError):
        await ledger.protect(lease, "child-a", {"model_tokens": 700})
    assert (await ledger.counters(lease.objective_id))["model_tokens"]["protected"] == 700
    call = await ledger.reserve(
        lease, "final-child", {"model_tokens": 500}, scope="child-a", phase="finalization"
    )
    await ledger.start(lease, call)
    assert not await ledger.release_hold(lease, "child-a")
    await ledger.settle(call, {"model_tokens": 50})
    assert await ledger.release_hold(lease, "child-a")
    assert (await ledger.counters(lease.objective_id))["model_tokens"]["protected"] == 100
    with pytest.raises(AccountingError, match="reopened"):
        await ledger.protect(lease, "child-a", {"model_tokens": 600})


async def test_uncertain_usage_survives_new_ledger_and_settles_without_double_charge(research_pool):
    ctx, _ = await accounting_context(research_pool, profile())
    ledger, lease = ctx.ledger, ctx.lease
    call = await ledger.reserve(lease, "model", {"model_tokens": 500, "model_requests": 1})
    assert await ledger.reserve(lease, "model", {"model_tokens": 500, "model_requests": 1}) == call
    with pytest.raises(AccountingError):
        await ledger.reserve(lease, "model", {"model_tokens": 499})
    await ledger.start(lease, call)
    await ledger.settle(call, {"model_requests": 1})
    with pytest.raises(AccountingError):
        await ledger.release(lease, call)
    fresh = type(ledger)(research_pool)
    assert (await fresh.counters(lease.objective_id))["model_tokens"]["reserved"] == 500
    await fresh.settle(call, {"model_tokens": 45})
    await fresh.settle(call, {"model_tokens": 45, "model_requests": 1})
    counts = await fresh.counters(lease.objective_id)
    assert counts["model_tokens"]["used"] == 45 and counts["model_tokens"]["reserved"] == 0
    assert counts["model_requests"]["used"] == 1


async def test_completed_scope_releases_unused_hold_but_retains_uncertain_call_cost(research_pool):
    ctx, _ = await accounting_context(research_pool, profile())
    ledger, lease = ctx.ledger, ctx.lease
    await ledger.protect(lease, "worker:a", {"model_tokens": 600})
    call = await ledger.reserve(
        lease,
        "malformed",
        {"model_tokens": 200, "model_requests": 1},
        scope="worker:a",
        phase="finalization",
    )
    await ledger.start(lease, call)
    await ledger.settle(call, {"model_requests": 1})
    assert await ledger.release_hold(lease, "worker:a")
    counts = await ledger.counters(lease.objective_id)
    assert counts["model_tokens"]["reserved"] == 200  # No refund of unknown usage.
    assert counts["model_tokens"]["protected"] == 100  # Root protection remains.
    await ledger.protect(lease, "worker:b", {"model_tokens": 600})
    with pytest.raises(BudgetExhausted):
        await ledger.reserve(lease, "overdraw", {"model_tokens": 101})
    await ledger.settle(call, {"model_tokens": 50})
    await ledger.settle(call, {"model_tokens": 50})
    counts = await ledger.counters(lease.objective_id)
    assert counts["model_tokens"]["used"] == 50
    assert counts["model_tokens"]["reserved"] == 0
    assert counts["model_tokens"]["protected"] == 700  # Closed worker:a is not re-protected.


async def test_overrun_records_receipt_and_blocks_new_work(research_pool):
    ctx, _ = await accounting_context(research_pool, profile())
    call = await ctx.ledger.reserve(ctx.lease, "underestimate", {"model_tokens": 100})
    await ctx.ledger.start(ctx.lease, call)
    with pytest.raises(AccountingError, match="exceeded"):
        await ctx.ledger.settle(call, {"model_tokens": 101})
    with pytest.raises(RunClosed, match="accounting"):
        await ctx.ledger.reserve(ctx.lease, "another", {"model_tokens": 1})
    async with research_pool.connection() as conn:
        record = await (
            await conn.execute("SELECT * FROM research_reservations WHERE id=%s", (call,))
        ).fetchone()
        assert record["receipt"] == {"model_tokens": 101}
        assert record["state"] == "uncertain"


async def test_deadline_and_stale_or_foreign_leases_reject_admission(research_pool):
    ctx, _ = await accounting_context(research_pool, profile())
    for invalid in (
        replace(ctx.lease, fence=2),
        replace(ctx.lease, owner=uuid4()),
        replace(ctx.lease, attempt_id=uuid4()),
    ):
        with pytest.raises(RunClosed, match="lease"):
            await ctx.ledger.reserve(invalid, "invalid", {"model_tokens": 1})
    async with research_pool.connection() as conn:
        await conn.execute(
            """UPDATE research_objectives SET created_at=now()-interval '10 seconds',
            exploration_deadline=now()-interval '1 second' WHERE id=%s""",
            (ctx.lease.objective_id,),
        )
    with pytest.raises(BudgetExhausted, match="deadline"):
        await ctx.ledger.reserve(ctx.lease, "late", {"model_tokens": 1})
    call = await ctx.ledger.reserve(
        ctx.lease, "finish", {"model_tokens": 100}, phase="finalization"
    )
    await ctx.ledger.start(ctx.lease, call)
    async with research_pool.connection() as conn:
        await conn.execute(
            "UPDATE research_objectives SET cancel_requested_at=now() WHERE id=%s",
            (ctx.lease.objective_id,),
        )
    await ctx.ledger.settle(call, {"model_tokens": 50})  # Late cost cannot disappear.
    with pytest.raises(RunClosed):
        await ctx.ledger.check(ctx.lease, "finalization")


async def test_document_counts_dedupe_pinned_versions_only(research_pool):
    ctx, _ = await accounting_context(research_pool)
    for i, refs in enumerate((["doc/v1"], ["doc/v1"], ["doc/v2"])):
        call = await ctx.ledger.reserve(ctx.lease, str(i), {"documents_opened": 1, "bytes": 100})
        await ctx.ledger.start(ctx.lease, call)
        await ctx.ledger.settle(
            call, {"documents_opened": 1, "bytes": 50}, documents={"documents_opened": refs}
        )
        await ctx.ledger.settle(
            call, {"documents_opened": 1, "bytes": 50}, documents={"documents_opened": refs}
        )
        with pytest.raises(AccountingError, match="receipt cannot be changed"):
            await ctx.ledger.settle(
                call,
                {"documents_opened": 1, "bytes": 50},
                documents={"documents_opened": ["changed/v1"]},
            )
        with pytest.raises(AccountingError, match="usage cannot be changed"):
            await ctx.ledger.settle(
                call, {"documents_opened": 1, "bytes": 49}, documents={"documents_opened": refs}
            )
    counters = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counters["documents_opened"]["used"] == 2
    assert counters["bytes"]["used"] == 150
