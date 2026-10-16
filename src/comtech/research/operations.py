"""Safe job progress and lifecycle-owned retention, independent of optional tracing."""

import asyncio
import logging

from ag_ui.core import CustomEvent

MIGRATION = """
ALTER TABLE app_runs ADD COLUMN result_expires_at timestamptz;
ALTER TABLE app_runs ADD COLUMN result_expired boolean NOT NULL DEFAULT false;
UPDATE app_runs SET result_expires_at=finished_at+interval '30 days'
WHERE execution_mode='background' AND finished_at IS NOT NULL;
"""


async def progress(pool, run_id):
    async with pool.connection() as conn:
        objective = await (
            await conn.execute(
                "SELECT id,pinned_versions FROM research_objectives WHERE run_id=%s",
                (run_id,),
            )
        ).fetchone()
        if not objective:
            return {}
        tasks = await (
            await conn.execute(
                "SELECT kind,state,input->>'analysis_mode' AS mode,count(*) AS count "
                "FROM research_tasks WHERE objective_id=%s "
                "GROUP BY kind,state,input->>'analysis_mode'",
                (objective["id"],),
            )
        ).fetchall()
        usage = await (
            await conn.execute(
                "SELECT metric,used,reserved,protected,ceiling FROM research_budget_counters "
                "WHERE objective_id=%s",
                (objective["id"],),
            )
        ).fetchall()
        coverage = await (
            await conn.execute(
                "SELECT kind,count(*) AS count FROM research_data_records WHERE objective_id=%s "
                "AND retained AND NOT expired GROUP BY kind",
                (objective["id"],),
            )
        ).fetchall()
    return {
        "objective_id": str(objective["id"]),
        "tasks": tasks,
        "source_versions": objective["pinned_versions"],
        "usage": {
            r["metric"]: {k: r[k] for k in ("used", "reserved", "protected", "ceiling")}
            for r in usage
        },
        "selected_coverage": coverage,
    }


class Activity:
    def __init__(self, delivery):
        self.delivery = delivery

    async def __call__(self, claim, stage, outcome=None):
        value = {
            "stage": stage,
            "objective_id": str(claim.lease.objective_id),
            "task_id": str(claim.lease.task_id),
            "attempt_id": str(claim.lease.attempt_id),
            "parent_task_id": str(claim.task["parent_id"]) if claim.task["parent_id"] else None,
            "route": claim.task["kind"],
            "analysis_mode": claim.task["input"].get("analysis_mode"),
        }
        if outcome:
            value.update(status=outcome.state, termination_reason=outcome.reason)
            if outcome.result and outcome.result.get("specialist") == "research":
                result = outcome.result["result"]
                value.update(
                    semantic_status=result["status"],
                    termination_reason=result["termination_reason"],
                )
        await self.delivery.progress(
            claim.lease,
            f"task:{claim.lease.attempt_id}:{stage}",
            CustomEvent(name="agent.activity", value=value),
        )


class Maintenance:
    def __init__(self, pool, checkpointer, broker, interval):
        self.pool, self.checkpointer, self.broker, self.interval = (
            pool,
            checkpointer,
            broker,
            interval,
        )

    async def __aenter__(self):
        self.task = asyncio.create_task(self.run())
        return self

    async def __aexit__(self, *args):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)

    async def prune(self):
        if self.broker:
            await self.broker.prune()
        async with self.pool.connection() as conn, conn.transaction():
            expired = await (
                await conn.execute(
                    "UPDATE app_runs SET result=NULL,result_expired=true "
                    "WHERE execution_mode='background' "
                    "AND status IN ('completed','failed','cancelled') AND NOT result_expired "
                    "AND result_expires_at<clock_timestamp() RETURNING id",
                )
            ).fetchall()
            ids = [r["id"] for r in expired]
            await conn.execute("DELETE FROM app_run_events WHERE run_id=ANY(%s)", (ids,))
            # Keep a terminal task tombstone, but expire copies of the final semantic result.
            await conn.execute(
                "UPDATE research_tasks SET result=NULL,continuation='{}'::jsonb "
                "WHERE objective_id IN (SELECT id FROM research_objectives WHERE run_id=ANY(%s))",
                (ids,),
            )
        # Research checkpoints have dedicated task keys. Conversation checkpoints may contain
        # later active turns and are intentionally not deleted as a side effect of one run expiring.
        async with self.pool.connection() as conn:
            tasks = await (
                await conn.execute(
                    "SELECT t.id FROM research_tasks t "
                    "JOIN research_objectives o ON o.id=t.objective_id "
                    "JOIN app_runs r ON r.id=o.run_id WHERE r.result_expired AND t.kind='research'",
                )
            ).fetchall()
        for task in tasks:
            await self.checkpointer.adelete_thread("research:" + str(task["id"]))

    async def run(self):
        while True:
            try:
                await self.prune()
            except Exception as error:
                logging.getLogger("comtech").warning(
                    "retention_failed", extra={"error_type": type(error).__name__}
                )
            await asyncio.sleep(self.interval)
