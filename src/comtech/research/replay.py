"""Persist bounded call outputs before graph advancement; never guess unknown outcomes."""

from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from comtech.agents.errors import InvalidModelOutput

from .ledger import AccountingError
from .queue import bounded


class SavedTransient(AccountingError):
    pass


class CallReplay:
    def __init__(self, ledger):
        self.ledger, self.pool = ledger, ledger.pool

    async def prepare(self, lease, key, phase):
        async with self.pool.connection() as conn, conn.transaction():
            await self.ledger._active(conn, lease, phase)
            row = await (
                await conn.execute(
                    "SELECT * FROM research_executions WHERE task_id=%s AND operation_key=%s",
                    (lease.task_id, key),
                )
            ).fetchone()
            if row:
                if row["state"] == "success":
                    return row, True
                if row["state"] == "failed":
                    if row["record"].get("invalid_output"):
                        raise InvalidModelOutput(row["record"]["invalid_output"])
                    if row["record"].get("retryable"):
                        raise SavedTransient("Recorded transient provider failure")
                    raise AccountingError("Recorded call failure")
                if not row["record"].get("safe_to_retry"):
                    raise AccountingError(
                        "Call outcome is pending or uncertain; reconciliation required"
                    )
                row = await (
                    await conn.execute(
                        """UPDATE research_executions SET attempt_id=%s,state='pending',record='{}'
                    WHERE id=%s RETURNING *""",
                        (lease.attempt_id, row["id"]),
                    )
                ).fetchone()
            else:
                row = await (
                    await conn.execute(
                        """INSERT INTO research_executions
                    (id,objective_id,task_id,attempt_id,operation_key,request_hash,state,record)
                    VALUES(%s,%s,%s,%s,%s,%s,'pending','{}') RETURNING *""",
                        (uuid4(), lease.objective_id, lease.task_id, lease.attempt_id, key, key),
                    )
                ).fetchone()
            return row, False

    async def attach(self, entry, reservation):
        async with self.pool.connection() as conn, conn.transaction():
            await self.ledger._lock(conn, entry["objective_id"])
            await conn.execute(
                "UPDATE research_executions SET record=%s WHERE id=%s",
                (Jsonb({"reservation_id": str(reservation)}), entry["id"]),
            )

    async def save(
        self,
        entry,
        reservation,
        actual,
        documents,
        *,
        output=None,
        retryable=False,
        success=True,
        invalid_output=None,
    ):
        record = bounded(
            {
                "reservation_id": str(reservation),
                "actual": actual,
                "documents": {k: sorted(v) for k, v in (documents or {}).items()},
                "output": output,
                "retryable": retryable,
                "invalid_output": invalid_output,
            }
        )
        async with self.pool.connection() as conn, conn.transaction():
            await self.ledger._lock(conn, entry["objective_id"])
            changed = await conn.execute(
                """UPDATE research_executions SET state=%s,record=%s
                WHERE id=%s AND attempt_id=%s AND state='pending'""",
                (
                    "success" if success else "failed",
                    Jsonb(record),
                    entry["id"],
                    entry["attempt_id"],
                ),
            )
            if not changed.rowcount:
                raise AccountingError("Execution ownership changed before output registration")

    async def reconcile_receipt(self, entry):
        record = entry["record"]
        await self.ledger.settle(
            UUID(record["reservation_id"]), record["actual"], documents=record.get("documents")
        )
