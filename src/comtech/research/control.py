"""Explicit cancellation, expiry, and singleton startup reconciliation."""

from uuid import UUID

from ag_ui.core import RunErrorEvent
from psycopg.types.json import Jsonb

from .ledger import AccountingError, Lease
from .replay import CallReplay

TERMINAL = ("completed", "failed", "cancelled")


class Control:
    def __init__(self, pool, delivery):
        self.pool, self.delivery, self.ledger = pool, delivery, delivery.ledger

    async def abort_locked(self, conn, objective, reason, *, cancelled=False):
        if objective["status"] in TERMINAL:
            return
        state = "cancelled" if cancelled else "failed"
        await conn.execute(
            "UPDATE research_data_capabilities SET revoked=true WHERE objective_id=%s",
            (objective["id"],),
        )
        await conn.execute(
            "UPDATE research_executions SET state=%s WHERE objective_id=%s "
            "AND state='running' AND record->>'kind'='python'",
            ("cancelled" if cancelled else "uncertain", objective["id"]),
        )
        await conn.execute(
            """UPDATE research_objectives SET cancel_requested_at=
            CASE WHEN %s THEN COALESCE(cancel_requested_at,clock_timestamp())
            ELSE cancel_requested_at END
            WHERE id=%s""",
            (cancelled, objective["id"]),
        )
        await conn.execute(
            """UPDATE research_tasks SET state=%s,termination_reason=%s,lease_owner=NULL,
            lease_expires_at=NULL,updated_at=clock_timestamp() WHERE objective_id=%s
            AND state NOT IN ('completed','failed','cancelled')""",
            (state, reason, objective["id"]),
        )
        await conn.execute(
            """UPDATE research_attempts SET state=%s,settled_at=clock_timestamp()
            WHERE objective_id=%s AND state='running'""",
            (state, objective["id"]),
        )
        await self.delivery.append_locked(
            conn,
            objective["run_id"],
            "terminal:0",
            RunErrorEvent(
                message="Run cancelled" if cancelled else "Run ended without an approved answer",
                code=reason.upper(),
            ),
        )
        await conn.execute(
            """UPDATE app_runs SET status=%s,terminal_reason=%s,finished_at=clock_timestamp(),
            result_expires_at=clock_timestamp()+interval '30 days'
            WHERE id=%s""",
            (state, reason, objective["run_id"]),
        )

    async def cancel(self, run_id):
        async with self.pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute("SELECT id FROM research_objectives WHERE run_id=%s", (run_id,))
            ).fetchone()
            if not row:
                raise ValueError("Background objective not found")
            objective = await self.ledger._lock(conn, row["id"])
            await self.abort_locked(conn, objective, "cancelled", cancelled=True)
            return objective["id"]

    async def sweep(self):
        async with self.pool.connection() as conn:
            ids = await (
                await conn.execute(
                    """SELECT o.id FROM research_objectives o JOIN app_runs r ON r.id=o.run_id
                WHERE r.status IN ('queued','running','waiting','cancel_requested','interrupted')
                AND (o.deadline<=clock_timestamp() OR o.accounting_error IS NOT NULL)"""
                )
            ).fetchall()
        for item in ids:
            async with self.pool.connection() as conn, conn.transaction():
                objective = await self.ledger._lock(conn, item["id"])
                await self.abort_locked(
                    conn,
                    objective,
                    "accounting_failure" if objective["accounting_error"] else "deadline",
                )

    async def recover(self, pinned_versions):
        """Only called before consumers start, while holding singleton API ownership."""
        await self.sweep()
        async with self.pool.connection() as conn:
            ids = await (
                await conn.execute(
                    """SELECT o.id FROM research_objectives o JOIN app_runs r ON r.id=o.run_id
                WHERE r.status IN ('queued','running','waiting','cancel_requested','interrupted')"""
                )
            ).fetchall()
        for item in ids:
            await self._recover_one(item["id"], pinned_versions)

    async def _recover_one(self, objective_id, pins):
        async with self.pool.connection() as conn, conn.transaction():
            objective = await self.ledger._lock(conn, objective_id)
            if objective["status"] in TERMINAL:
                return
            if objective["cancel_requested_at"] or objective["status"] == "cancel_requested":
                await self.abort_locked(conn, objective, "cancelled", cancelled=True)
                return
            if objective["pinned_versions"] != pins:
                await self.abort_locked(conn, objective, "source_versions_unavailable")
                return
            executions = await (
                await conn.execute(
                    "SELECT * FROM research_executions WHERE objective_id=%s", (objective_id,)
                )
            ).fetchall()
            reservations = await (
                await conn.execute(
                    """SELECT r.*,a.owner,a.fence FROM research_reservations r
                JOIN research_attempts a ON a.id=r.attempt_id WHERE r.objective_id=%s""",
                    (objective_id,),
                )
            ).fetchall()
        replay = CallReplay(self.ledger)
        known = set()
        for entry in executions:
            if entry["state"] in ("success", "failed") and "actual" in entry["record"]:
                known.add(UUID(entry["record"]["reservation_id"]))
                try:
                    await replay.reconcile_receipt(entry)
                except AccountingError:
                    async with self.pool.connection() as conn, conn.transaction():
                        objective = await self.ledger._lock(conn, objective_id)
                        await self.abort_locked(conn, objective, "accounting_failure")
                    return
        uncertain = False
        for row in reservations:
            if row["state"] == "reserved":
                await self.ledger.release(
                    Lease(
                        objective_id, row["task_id"], row["attempt_id"], row["owner"], row["fence"]
                    ),
                    row["id"],
                )
            elif row["state"] in ("inflight", "uncertain") and row["id"] not in known:
                uncertain = True
        async with self.pool.connection() as conn, conn.transaction():
            objective = await self.ledger._lock(conn, objective_id)
            if uncertain:
                await self.abort_locked(conn, objective, "uncertain_external_completion")
                return
            await conn.execute(
                "UPDATE research_executions SET record=%s "
                "WHERE objective_id=%s AND state='pending'",
                (Jsonb({"safe_to_retry": True}), objective_id),
            )
            await conn.execute(
                """UPDATE research_attempts SET state='settled',settled_at=clock_timestamp()
                WHERE objective_id=%s AND state='running'""",
                (objective_id,),
            )
            await conn.execute(
                """UPDATE research_tasks SET state='pending',lease_owner=NULL,lease_expires_at=NULL,
                continuation=continuation || '{"recover":true}'::jsonb,updated_at=clock_timestamp()
                WHERE objective_id=%s AND state IN ('running','finalizing')""",
                (objective_id,),
            )
            await conn.execute(
                "UPDATE app_runs SET status='queued' WHERE id=%s", (objective["run_id"],)
            )
