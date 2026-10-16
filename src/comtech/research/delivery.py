"""Transactional background event sequencing and terminal answer publication."""

import json

from ag_ui.core import (
    RunErrorEvent,
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from psycopg.types.json import Jsonb

from .ledger import AccountingError, Ledger

MIGRATION = """
ALTER TABLE app_run_events ADD COLUMN operation_key text;
CREATE UNIQUE INDEX app_run_event_operation ON app_run_events(run_id,operation_key)
    WHERE operation_key IS NOT NULL;
"""


class Delivery:
    def __init__(self, pool):
        self.pool, self.ledger = pool, Ledger(pool)

    async def append_locked(self, conn, run_id, key, event):
        payload = json.loads(event.model_dump_json(by_alias=True, exclude_none=True))
        prior = await (
            await conn.execute(
                "SELECT payload FROM app_run_events WHERE run_id=%s AND operation_key=%s",
                (run_id, key),
            )
        ).fetchone()
        if prior:
            if prior["payload"] != payload:
                raise AccountingError("Event identity cannot change its payload")
            return
        row = await (
            await conn.execute(
                "UPDATE app_runs SET event_sequence=event_sequence+1 "
                "WHERE id=%s RETURNING event_sequence",
                (run_id,),
            )
        ).fetchone()
        await conn.execute(
            "INSERT INTO app_run_events(run_id,sequence,payload,operation_key) VALUES(%s,%s,%s,%s)",
            (run_id, row["event_sequence"], Jsonb(payload), key),
        )

    async def progress(self, lease, key, event):
        # All message/terminal events are committed only in terminal_locked.
        if event.type not in ("RUN_STARTED", "STEP_STARTED", "STEP_FINISHED", "CUSTOM"):
            raise ValueError("Not a progress event")
        async with self.pool.connection() as conn, conn.transaction():
            objective = await self.ledger._active(conn, lease, "finalization")
            await self.append_locked(conn, objective["run_id"], key, event)

    async def terminal_locked(self, conn, lease, objective, outcome):
        task = await (
            await conn.execute(
                "SELECT kind,parent_id FROM research_tasks WHERE id=%s", (lease.task_id,)
            )
        ).fetchone()
        if task["kind"] != "supervisor" or task["parent_id"] is not None:
            return
        run_id = objective["run_id"]
        result = outcome["result"]
        if outcome["state"] == "completed":
            if not result or not result.get("answer") or result.get("review_status") != "approved":
                raise AccountingError("Root publication requires a reviewed answer")
            events = [
                TextMessageStartEvent(message_id=str(run_id), role="assistant"),
                TextMessageContentEvent(message_id=str(run_id), delta=result["answer"]),
                TextMessageEndEvent(message_id=str(run_id)),
                RunFinishedEvent(thread_id=str(objective["thread_id"]), run_id=str(run_id)),
            ]
        else:
            events = [
                RunErrorEvent(
                    message="Assistant run ended without an approved answer",
                    code="EXECUTION_FAILED",
                )
            ]
        for index, event in enumerate(events):
            await self.append_locked(conn, run_id, f"terminal:{index}", event)
        await conn.execute(
            """UPDATE app_runs SET status=%s,result=%s,terminal_reason=%s,
            finished_at=clock_timestamp(),result_expires_at=clock_timestamp()+interval '30 days'
            WHERE id=%s""",
            (
                outcome["state"],
                Jsonb(result) if result is not None else None,
                outcome["reason"] or "completed",
                run_id,
            ),
        )
