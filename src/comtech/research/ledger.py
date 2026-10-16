"""Atomic admission and settlement. Never hold these transactions across external I/O."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from comtech.agents.budget import digest, serialized

from .budgets import BudgetProfile


class AccountingError(RuntimeError):
    pass


class BudgetExhausted(AccountingError):
    def __init__(self, reason="objective_budget"):
        self.reason = reason
        super().__init__(reason)


class RunClosed(AccountingError):
    pass


@dataclass(frozen=True)
class Lease:
    objective_id: UUID
    task_id: UUID
    attempt_id: UUID
    owner: UUID
    fence: int


def amounts(values):
    if any(type(v) is not int or v < 0 for v in values.values()):
        raise ValueError("Usage must contain nonnegative integer amounts")
    return dict(values)


async def initialize_budget(conn, objective_id, profile):
    """Called in the submission transaction. Never reinitialize a recovered ledger."""
    profile = BudgetProfile.model_validate(profile)
    for metric, ceiling in profile.limits.items():
        await conn.execute(
            """INSERT INTO research_budget_counters(objective_id,metric,ceiling,protected)
            VALUES(%s,%s,%s,%s)""",
            (objective_id, metric, ceiling, profile.final_reserve.get(metric, 0)),
        )
    await conn.execute(
        "INSERT INTO research_budget_holds(objective_id,scope_key,allocation) "
        "VALUES(%s,'supervisor',%s)",
        (objective_id, Jsonb(profile.final_reserve)),
    )
    for metric, value in profile.final_reserve.items():
        await conn.execute(
            "INSERT INTO research_hold_amounts VALUES(%s,'supervisor',%s,%s)",
            (objective_id, metric, value),
        )


class Ledger:
    def __init__(self, pool):
        self.pool = pool

    async def _lock(self, conn, objective_id):
        row = await (
            await conn.execute(
                """SELECT o.*,r.status,clock_timestamp() AS now FROM research_objectives o
            JOIN app_runs r ON r.id=o.run_id WHERE o.id=%s FOR UPDATE OF o,r""",
                (objective_id,),
            )
        ).fetchone()
        if row is None:
            raise RunClosed("Unknown objective")
        return row

    async def _active(self, conn, lease, phase):
        row = await self._lock(conn, lease.objective_id)
        if row["cancel_requested_at"] or row["status"] not in ("queued", "running", "waiting"):
            raise RunClosed("Run is not active")
        if row["accounting_error"] or row["now"] >= row["deadline"]:
            raise RunClosed("Objective deadline or accounting failure")
        valid = await (
            await conn.execute(
                """SELECT 1 FROM research_tasks t JOIN research_attempts a
            ON a.task_id=t.id AND a.objective_id=t.objective_id
            WHERE t.id=%s AND t.objective_id=%s AND a.id=%s AND a.owner=%s
            AND a.fence=%s AND t.fence=a.fence AND t.lease_owner=a.owner
            AND t.lease_expires_at>clock_timestamp() AND a.state='running'
            AND t.state IN ('running','finalizing')""",
                (lease.task_id, lease.objective_id, lease.attempt_id, lease.owner, lease.fence),
            )
        ).fetchone()
        if not valid:
            raise RunClosed("Expired or stale task lease")
        if phase == "exploration" and row["now"] >= row["exploration_deadline"]:
            raise BudgetExhausted("deadline")
        return row

    async def check(self, lease, phase="exploration"):
        async with self.pool.connection() as conn, conn.transaction():
            return await self._active(conn, lease, phase)

    async def protect(self, lease, scope, allocation, charge=None):
        async with self.pool.connection() as conn, conn.transaction():
            await self._active(conn, lease, "exploration")
            await self.protect_locked(conn, lease, scope, allocation, charge)

    async def protect_locked(self, conn, lease, scope, allocation, charge=None):
        """Caller holds the objective lock and has validated the active lease."""
        allocation = amounts(allocation)
        prior = await (
            await conn.execute(
                "SELECT * FROM research_budget_holds WHERE objective_id=%s AND scope_key=%s",
                (lease.objective_id, scope),
            )
        ).fetchone()
        if prior:
            if prior["allocation"] != allocation or prior["closed"]:
                raise AccountingError("Protected allocation cannot be changed or reopened")
            return
        for metric, value in amounts(charge or {}).items():
            changed = await conn.execute(
                """UPDATE research_budget_counters SET used=used+%s
                WHERE objective_id=%s AND metric=%s AND used+reserved+protected+%s<=ceiling""",
                (value, lease.objective_id, metric, value),
            )
            if not changed.rowcount:
                raise BudgetExhausted()
        await conn.execute(
            "INSERT INTO research_budget_holds(objective_id,scope_key,allocation) VALUES(%s,%s,%s)",
            (lease.objective_id, scope, Jsonb(allocation)),
        )
        for metric, value in allocation.items():
            changed = await conn.execute(
                """UPDATE research_budget_counters SET protected=protected+%s
                WHERE objective_id=%s AND metric=%s AND used+reserved+protected+%s<=ceiling""",
                (value, lease.objective_id, metric, value),
            )
            if not changed.rowcount:
                raise BudgetExhausted()
            await conn.execute(
                "INSERT INTO research_hold_amounts VALUES(%s,%s,%s,%s)",
                (lease.objective_id, scope, metric, value),
            )

    async def release_hold(self, lease, scope):
        async with self.pool.connection() as conn, conn.transaction():
            await self._active(conn, lease, "finalization")
            return await self.release_hold_locked(conn, lease, scope)

    async def release_hold_locked(self, conn, lease, scope):
        """Release unused finalization capacity; unknown incurred usage stays reserved."""
        pending = await (
            await conn.execute(
                """SELECT 1 FROM research_reservations WHERE objective_id=%s AND scope_key=%s
            AND state IN ('reserved','inflight') LIMIT 1""",
                (lease.objective_id, scope),
            )
        ).fetchone()
        if pending:
            return False
        rows = await (
            await conn.execute(
                "SELECT * FROM research_hold_amounts WHERE objective_id=%s AND scope_key=%s",
                (lease.objective_id, scope),
            )
        ).fetchall()
        for row in rows:
            await conn.execute(
                """UPDATE research_budget_counters SET protected=protected-%s
                WHERE objective_id=%s AND metric=%s""",
                (row["remaining"], lease.objective_id, row["metric"]),
            )
        await conn.execute(
            "UPDATE research_hold_amounts SET remaining=0 WHERE objective_id=%s AND scope_key=%s",
            (lease.objective_id, scope),
        )
        await conn.execute(
            "UPDATE research_budget_holds SET closed=true WHERE objective_id=%s AND scope_key=%s",
            (lease.objective_id, scope),
        )
        return True

    async def reserve(self, lease, key, requested, *, scope="supervisor", phase="exploration"):
        requested = amounts(requested)
        if phase not in ("exploration", "finalization"):
            raise ValueError("Invalid accounting phase")
        request_hash = digest(serialized([scope, phase, requested]))
        async with self.pool.connection() as conn, conn.transaction():
            await self._active(conn, lease, phase)
            prior = await (
                await conn.execute(
                    "SELECT * FROM research_reservations WHERE attempt_id=%s AND operation_key=%s",
                    (lease.attempt_id, key),
                )
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise AccountingError("Reservation identity reused with different amounts")
                return prior["id"]
            reservation = uuid4()
            await conn.execute(
                """INSERT INTO research_reservations
                (id,objective_id,task_id,attempt_id,operation_key,phase,state,scope_key,request_hash)
                VALUES(%s,%s,%s,%s,%s,%s,'reserved',%s,%s)""",
                (
                    reservation,
                    lease.objective_id,
                    lease.task_id,
                    lease.attempt_id,
                    key,
                    phase,
                    scope,
                    request_hash,
                ),
            )
            for metric, value in requested.items():
                draw = 0
                if phase == "finalization":
                    held = await (
                        await conn.execute(
                            """SELECT remaining FROM research_hold_amounts
                        WHERE objective_id=%s AND scope_key=%s AND metric=%s""",
                            (lease.objective_id, scope, metric),
                        )
                    ).fetchone()
                    draw = min(value, held["remaining"] if held else 0)
                changed = await conn.execute(
                    """UPDATE research_budget_counters SET reserved=reserved+%s,
                    protected=protected-%s
                    WHERE objective_id=%s AND metric=%s
                    AND used+reserved+protected+%s-%s<=ceiling""",
                    (value, draw, lease.objective_id, metric, value, draw),
                )
                if not changed.rowcount:
                    raise BudgetExhausted()
                if draw:
                    await conn.execute(
                        """UPDATE research_hold_amounts SET remaining=remaining-%s
                        WHERE objective_id=%s AND scope_key=%s AND metric=%s""",
                        (draw, lease.objective_id, scope, metric),
                    )
                await conn.execute(
                    """INSERT INTO research_reservation_amounts
                    (objective_id,reservation_id,metric,amount,protected_draw)
                    VALUES(%s,%s,%s,%s,%s)""",
                    (lease.objective_id, reservation, metric, value, draw),
                )
            return reservation

    async def start(self, lease, reservation):
        async with self.pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    "SELECT * FROM research_reservations WHERE id=%s",
                    (reservation,),
                )
            ).fetchone()
            if not row or row["attempt_id"] != lease.attempt_id:
                raise AccountingError("Reservation does not belong to this attempt")
            objective = await self._active(conn, lease, row["phase"])
            changed = await conn.execute(
                "UPDATE research_reservations SET state='inflight' "
                "WHERE id=%s AND state='reserved'",
                (reservation,),
            )
            if not changed.rowcount:
                raise AccountingError("Reservation already dispatched or settled")
            return objective["deadline"]

    async def settle(self, reservation, actual, *, documents=None):
        """Missing metrics stay reserved. Late usage is recorded even for stale/cancelled work."""
        actual = amounts(actual)
        overrun = False
        async with self.pool.connection() as conn, conn.transaction():
            entry = await (
                await conn.execute(
                    "SELECT * FROM research_reservations WHERE id=%s",
                    (reservation,),
                )
            ).fetchone()
            if not entry:
                raise AccountingError("Unknown reservation")
            await self._lock(conn, entry["objective_id"])
            entry = await (
                await conn.execute(
                    "SELECT * FROM research_reservations WHERE id=%s",
                    (reservation,),
                )
            ).fetchone()
            if entry["state"] not in ("inflight", "uncertain", "settled"):
                raise AccountingError("Cannot settle an undispatched or released reservation")
            rows = await (
                await conn.execute(
                    "SELECT * FROM research_reservation_amounts WHERE reservation_id=%s",
                    (reservation,),
                )
            ).fetchall()
            if not set(actual).issubset(r["metric"] for r in rows):
                raise AccountingError("Receipt contains unreserved counters")
            if documents:
                document_receipt = {k: sorted(set(v)) for k, v in documents.items()}
                if not set(documents).issubset(
                    {"documents_discovered", "documents_opened"} & set(actual)
                ):
                    raise AccountingError("Invalid document accounting receipt")
                if (
                    entry["document_receipt"] is not None
                    and entry["document_receipt"] != document_receipt
                ):
                    raise AccountingError("Document receipt cannot be changed")
                await conn.execute(
                    "UPDATE research_reservations SET document_receipt=%s WHERE id=%s",
                    (Jsonb(document_receipt), reservation),
                )
            hold = await (
                await conn.execute(
                    "SELECT closed FROM research_budget_holds "
                    "WHERE objective_id=%s AND scope_key=%s",
                    (entry["objective_id"], entry["scope_key"]),
                )
            ).fetchone()
            for row in rows:
                metric = row["metric"]
                if metric not in actual:
                    continue
                value = actual[metric]
                if row["actual"] is not None:
                    if value != row["actual"] and metric not in (documents or {}):
                        raise AccountingError("Settled usage cannot be changed")
                    continue
                if documents and metric in documents:
                    value = 0
                    for key in set(documents[metric]):
                        inserted = await conn.execute(
                            "INSERT INTO research_document_usage VALUES(%s,%s,%s) "
                            "ON CONFLICT DO NOTHING",
                            (entry["objective_id"], metric, key),
                        )
                        value += inserted.rowcount
                if value > row["amount"]:
                    overrun = True
                    continue
                # A completed scope can close while a finished provider call's token
                # usage is unknown. Its full call reservation remains until this receipt;
                # a later settlement must not recreate unused finalization capacity.
                refund = max(0, row["protected_draw"] - value) if hold and not hold["closed"] else 0
                await conn.execute(
                    """UPDATE research_budget_counters SET reserved=reserved-%s,
                    used=used+%s,protected=protected+%s WHERE objective_id=%s AND metric=%s""",
                    (row["amount"], value, refund, entry["objective_id"], metric),
                )
                if refund:
                    await conn.execute(
                        """UPDATE research_hold_amounts SET remaining=remaining+%s
                        WHERE objective_id=%s AND scope_key=%s AND metric=%s""",
                        (refund, entry["objective_id"], entry["scope_key"], metric),
                    )
                await conn.execute(
                    "UPDATE research_reservation_amounts SET actual=%s "
                    "WHERE reservation_id=%s AND metric=%s",
                    (value, reservation, metric),
                )
            pending = await (
                await conn.execute(
                    "SELECT 1 FROM research_reservation_amounts "
                    "WHERE reservation_id=%s AND actual IS NULL LIMIT 1",
                    (reservation,),
                )
            ).fetchone()
            await conn.execute(
                "UPDATE research_reservations SET state=%s,receipt=%s,settled_at=now() WHERE id=%s",
                ("uncertain" if pending else "settled", Jsonb(actual), reservation),
            )
            # A sufficient parent may retire a child while external work settles. Release
            # unused finalization capacity once calls end; unknown incurred usage stays reserved.
            retired = await (
                await conn.execute(
                    "SELECT t.scope_key,a.owner,a.fence FROM research_tasks t "
                    "JOIN research_attempts a ON a.id=%s WHERE t.id=%s "
                    "AND t.state IN ('completed','failed','cancelled')",
                    (entry["attempt_id"], entry["task_id"]),
                )
            ).fetchone()
            if retired:
                await self.release_hold_locked(
                    conn,
                    Lease(
                        entry["objective_id"],
                        entry["task_id"],
                        entry["attempt_id"],
                        retired["owner"],
                        retired["fence"],
                    ),
                    retired["scope_key"],
                )
            if overrun:
                await conn.execute(
                    "UPDATE research_objectives SET accounting_error='usage_exceeded_reservation' "
                    "WHERE id=%s",
                    (entry["objective_id"],),
                )
        if overrun:
            raise AccountingError("Actual usage exceeded reservation; objective closed")

    async def release(self, lease, reservation):
        async with self.pool.connection() as conn, conn.transaction():
            await self._lock(conn, lease.objective_id)
            entry = await (
                await conn.execute(
                    "SELECT * FROM research_reservations WHERE id=%s",
                    (reservation,),
                )
            ).fetchone()
            if not entry or entry["attempt_id"] != lease.attempt_id or entry["state"] != "reserved":
                raise AccountingError("Only undispatched reservations can be released")
            rows = await (
                await conn.execute(
                    "SELECT * FROM research_reservation_amounts WHERE reservation_id=%s",
                    (reservation,),
                )
            ).fetchall()
            for row in rows:
                await conn.execute(
                    """UPDATE research_budget_counters SET reserved=reserved-%s,
                    protected=protected+%s
                    WHERE objective_id=%s AND metric=%s""",
                    (row["amount"], row["protected_draw"], lease.objective_id, row["metric"]),
                )
                await conn.execute(
                    """UPDATE research_hold_amounts SET remaining=remaining+%s
                    WHERE objective_id=%s AND scope_key=%s AND metric=%s""",
                    (row["protected_draw"], lease.objective_id, entry["scope_key"], row["metric"]),
                )
            await conn.execute(
                "UPDATE research_reservations SET state='released' WHERE id=%s", (reservation,)
            )

    async def counters(self, objective_id):
        async with self.pool.connection() as conn:
            return {
                r["metric"]: r
                for r in await (
                    await conn.execute(
                        "SELECT * FROM research_budget_counters WHERE objective_id=%s",
                        (objective_id,),
                    )
                ).fetchall()
            }
