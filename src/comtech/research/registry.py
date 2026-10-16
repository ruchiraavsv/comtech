"""Transactional submission and canonical identity for background work.

Called only by trusted application code. No scheduler, HTTP feature or research
tool is enabled by this module alone.
"""

from datetime import timedelta
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from comtech.agents.budget import digest, serialized

from .budgets import BudgetProfile
from .contracts import SourceScope
from .ledger import initialize_budget


class ActiveRunError(ValueError):
    pass


class SubmissionConflict(ValueError):
    pass


class JobRegistry:
    def __init__(self, pool):
        self.pool = pool

    async def submit(
        self,
        *,
        thread_id: UUID,
        idempotency_key: str,
        message: str,
        scope: SourceScope,
        budget_profile: dict,
        duration_seconds=1800,
        finalization_seconds=180,
        graph_version=2,
    ):
        if not 1 <= len(idempotency_key) <= 200 or not message.strip() or len(message) > 4000:
            raise ValueError("Invalid submission key or message")
        if not 0 < finalization_seconds < duration_seconds:
            raise ValueError("Deadline must protect finalization time")
        body = {"thread_id": str(thread_id), "message": message, "execution_mode": "background"}
        request_hash = digest(serialized(body))
        try:
            async with self.pool.connection() as conn, conn.transaction():
                # Serialize even when no run row exists yet. Unique indexes remain the
                # final authority, including conflicts with legacy stream admission.
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 72610303))",
                    (str(thread_id),),
                )
                previous = await (
                    await conn.execute(
                        "SELECT * FROM app_runs WHERE thread_id=%s AND idempotency_key=%s",
                        (thread_id, idempotency_key),
                    )
                ).fetchone()
                if previous:
                    if previous["request_hash"] != request_hash:
                        raise SubmissionConflict("Idempotency key is bound to another request")
                    return previous, False
                row = await (await conn.execute("SELECT now() AS now")).fetchone()
                created = row["now"]
                run_id, objective_id, task_id = uuid4(), uuid4(), uuid4()
                profile = BudgetProfile.model_validate(budget_profile).model_dump()
                run = await (
                    await conn.execute(
                        """INSERT INTO app_runs
                    (id,thread_id,request_id,trace_id,status,execution_mode,graph_run_id,
                     graph_version,idempotency_key,request_hash,input)
                    VALUES(%s,%s,%s,%s,'queued','background',%s,%s,%s,%s,%s) RETURNING *""",
                        (
                            run_id,
                            thread_id,
                            uuid4(),
                            uuid4(),
                            run_id,
                            graph_version,
                            idempotency_key,
                            request_hash,
                            Jsonb(body),
                        ),
                    )
                ).fetchone()
                await conn.execute(
                    """INSERT INTO research_objectives
                    (id,run_id,thread_id,scope,pinned_versions,budget_profile,created_at,
                     exploration_deadline,deadline) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        objective_id,
                        run_id,
                        thread_id,
                        Jsonb(scope.model_dump(mode="json")),
                        Jsonb(scope.pinned_versions),
                        Jsonb(profile),
                        created,
                        created + timedelta(seconds=duration_seconds - finalization_seconds),
                        created + timedelta(seconds=duration_seconds),
                    ),
                )
                await conn.execute(
                    """INSERT INTO research_tasks(id,objective_id,logical_key,kind,input)
                    VALUES(%s,%s,'supervisor','supervisor',%s)""",
                    (
                        task_id,
                        objective_id,
                        Jsonb({"message": message, "graph_version": graph_version}),
                    ),
                )
                await initialize_budget(conn, objective_id, profile)
                return run, True
        except UniqueViolation as error:
            if error.diag.constraint_name == "app_runs_one_active_thread":
                raise ActiveRunError("A run is already active in this conversation") from None
            raise

    async def objective(self, run_id):
        async with self.pool.connection() as conn:
            return await (
                await conn.execute(
                    "SELECT * FROM research_objectives WHERE run_id=%s",
                    (run_id,),
                )
            ).fetchone()


def validate_checkpoint_identity(snapshot, run, objective_id):
    """Recovery must not resume a different run or reinterpret an old graph."""
    config = snapshot.config.get("configurable", {}) if snapshot.config else {}
    values = snapshot.values
    if (
        str(config.get("thread_id")) != str(run["thread_id"])
        or str(values.get("run_id")) != str(run["graph_run_id"])
        or values.get("graph_version") != run["graph_version"]
        or str(values.get("objective_id")) != str(objective_id)
    ):
        raise ValueError("Checkpoint does not belong to the canonical run/thread/graph")
