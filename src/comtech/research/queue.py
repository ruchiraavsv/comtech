"""Trusted durable task queue. Research proposal/scope validation belongs to R5.

Every mutation locks the objective before its tasks, matching the budget ledger.
No transaction spans a handler or external operation.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from comtech.agents.budget import digest, serialized

from .ledger import AccountingError, Lease, Ledger

TERMINAL = ("completed", "failed", "cancelled")


def bounded(value):
    if len(serialized(value).encode("utf-8")) > 128 * 1024:
        raise ValueError("Task state exceeds the compact continuation/result limit")
    return value


@dataclass(frozen=True)
class Claim:
    lease: Lease
    task: dict
    objective: dict
    dependencies: list[dict]


class TaskQueue:
    def __init__(self, pool, *, lease_seconds=60, max_runs=2, per_run=2, terminal_commit=None):
        if lease_seconds <= 0 or max_runs < 1 or per_run < 1:
            raise ValueError("Scheduler limits must be positive")
        self.pool, self.ledger = pool, Ledger(pool)
        self.lease_seconds, self.max_runs, self.per_run = lease_seconds, max_runs, per_run
        self.terminal_commit = terminal_commit

    async def enqueue(self, lease, key, kind, payload, allocation):
        """Internal admission only; callers supply validated work and finalization bounds."""
        if kind not in ("knowledge_worker", "research") or not key or len(key) > 200:
            raise ValueError("Invalid task kind or logical key")
        request_hash = digest(serialized([kind, bounded(payload), allocation]))
        async with self.pool.connection() as conn, conn.transaction():
            await self.ledger._active(conn, lease, "exploration")
            previous = await (
                await conn.execute(
                    "SELECT * FROM research_tasks WHERE objective_id=%s AND logical_key=%s",
                    (lease.objective_id, key),
                )
            ).fetchone()
            if previous:
                if previous["admission_hash"] != request_hash:
                    raise AccountingError("Task key is bound to different work")
                return previous
            task_id = uuid4()
            scope = "task:" + str(task_id)
            parent = await (
                await conn.execute("SELECT kind FROM research_tasks WHERE id=%s", (lease.task_id,))
            ).fetchone()
            charge = {"research_tasks" if kind == "research" else "specialist_calls": 1}
            if kind == "research" and parent["kind"] == "supervisor":
                charge["specialist_calls"] = 1
            await self.ledger.protect_locked(
                conn,
                lease,
                scope,
                allocation,
                charge,
            )
            return await (
                await conn.execute(
                    """INSERT INTO research_tasks
                    (id,objective_id,parent_id,logical_key,kind,input,admission_hash,scope_key)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (
                        task_id,
                        lease.objective_id,
                        lease.task_id,
                        key,
                        kind,
                        Jsonb(payload),
                        request_hash,
                        scope,
                    ),
                )
            ).fetchone()

    async def claim(self, owner, kinds):
        if not kinds:
            return None
        async with self.pool.connection() as conn, conn.transaction():
            # Serialize admission across objectives, including global active-run capacity.
            await conn.execute("SELECT pg_advisory_xact_lock(72610304)")
            candidates = await (
                await conn.execute(
                    """SELECT t.id,t.objective_id FROM research_tasks t
                    JOIN research_objectives o ON o.id=t.objective_id
                    JOIN app_runs r ON r.id=o.run_id
                    WHERE t.state='pending' AND t.kind=ANY(%s)
                    AND r.status IN ('queued','running','waiting')
                    AND o.cancel_requested_at IS NULL AND o.accounting_error IS NULL
                    AND o.deadline>clock_timestamp()
                    ORDER BY (t.fence>0) DESC,t.updated_at,t.created_at,t.id""",
                    (list(kinds),),
                )
            ).fetchall()
            for candidate in candidates:
                objective = await self.ledger._lock(conn, candidate["objective_id"])
                if (
                    objective["status"] not in ("queued", "running", "waiting")
                    or objective["cancel_requested_at"]
                    or objective["accounting_error"]
                    or objective["now"] >= objective["deadline"]
                ):
                    continue
                if objective["status"] == "queued":
                    active = await (
                        await conn.execute(
                            """SELECT count(*) AS n FROM app_runs WHERE execution_mode='background'
                            AND status IN ('running','waiting','cancel_requested','interrupted')"""
                        )
                    ).fetchone()
                    if active["n"] >= self.max_runs:
                        continue
                running = await (
                    await conn.execute(
                        """SELECT count(*) AS n FROM research_tasks WHERE objective_id=%s
                        AND state IN ('running','finalizing')""",
                        (objective["id"],),
                    )
                ).fetchone()
                if running["n"] >= self.per_run:
                    continue
                task = await (
                    await conn.execute(
                        """UPDATE research_tasks SET state='running',fence=fence+1,
                        lease_owner=%s,lease_expires_at=
                        LEAST(%s,clock_timestamp()+%s*interval '1 second'),
                        updated_at=clock_timestamp() WHERE id=%s AND state='pending' RETURNING *""",
                        (owner, objective["deadline"], self.lease_seconds, candidate["id"]),
                    )
                ).fetchone()
                if task is None:
                    continue
                attempt = uuid4()
                await conn.execute(
                    """INSERT INTO research_attempts(id,objective_id,task_id,fence,owner,state)
                    VALUES(%s,%s,%s,%s,%s,'running')""",
                    (attempt, objective["id"], task["id"], task["fence"], owner),
                )
                await conn.execute(
                    "UPDATE app_runs SET status='running' WHERE id=%s", (objective["run_id"],)
                )
                dependencies = await (
                    await conn.execute(
                        """SELECT t.id,t.logical_key,t.state,t.result,t.termination_reason
                        FROM research_dependencies d JOIN research_tasks t ON t.id=d.child_id
                        WHERE d.objective_id=%s AND d.parent_id=%s AND d.active
                        AND t.state=ANY(%s) ORDER BY t.id""",
                        (objective["id"], task["id"], list(TERMINAL)),
                    )
                ).fetchall()
                await conn.execute(
                    """UPDATE research_dependencies SET delivered=true
                    WHERE objective_id=%s AND parent_id=%s AND child_id=ANY(%s)""",
                    (objective["id"], task["id"], [d["id"] for d in dependencies]),
                )
                return Claim(
                    Lease(objective["id"], task["id"], attempt, owner, task["fence"]),
                    task,
                    objective,
                    dependencies,
                )
        return None

    async def heartbeat(self, lease):
        async with self.pool.connection() as conn, conn.transaction():
            objective = await self.ledger._active(conn, lease, "finalization")
            await conn.execute(
                """UPDATE research_tasks SET lease_expires_at=
                LEAST(%s,clock_timestamp()+%s*interval '1 second') WHERE id=%s""",
                (objective["deadline"], self.lease_seconds, lease.task_id),
            )

    async def _replay(self, conn, lease, request_hash):
        prior = await (
            await conn.execute(
                """SELECT x.*,a.owner,a.fence FROM research_task_transitions x
                JOIN research_attempts a ON a.id=x.attempt_id WHERE x.attempt_id=%s""",
                (lease.attempt_id,),
            )
        ).fetchone()
        if prior:
            if (
                prior["objective_id"] != lease.objective_id
                or prior["task_id"] != lease.task_id
                or prior["owner"] != lease.owner
                or prior["fence"] != lease.fence
                or prior["request_hash"] != request_hash
            ):
                raise AccountingError("Attempt transition cannot be changed")
            return prior["outcome"]

    async def transition(
        self, lease, *, state, result=None, dependencies=(), continuation=None, reason=None
    ):
        """Commit one immutable transition per attempt and atomically wake waiters."""
        if state not in (*TERMINAL, "waiting_children"):
            raise ValueError("Invalid task transition")
        deps = sorted(set(UUID(str(d)) for d in dependencies))
        if state == "waiting_children" and (not deps or result is not None):
            raise ValueError("Waiting requires dependencies and no semantic result")
        if state != "waiting_children" and deps:
            raise ValueError("Terminal task cannot wait")
        outcome = bounded(
            {
                "state": state,
                "result": result,
                "dependencies": list(map(str, deps)),
                "continuation": continuation or {},
                "reason": reason,
            }
        )
        request_hash = digest(serialized(outcome))
        async with self.pool.connection() as conn, conn.transaction():
            await self.ledger._lock(conn, lease.objective_id)
            replay = await self._replay(conn, lease, request_hash)
            if replay is not None:
                return replay
            objective = await self.ledger._active(conn, lease, "finalization")
            pending = await (
                await conn.execute(
                    """SELECT 1 FROM research_reservations WHERE attempt_id=%s
                    AND state IN ('reserved','inflight') LIMIT 1""",
                    (lease.attempt_id,),
                )
            ).fetchone()
            if pending:
                raise AccountingError(
                    "Cannot release task ownership while operations are in flight"
                )
            if state in TERMINAL:
                task = await (
                    await conn.execute(
                        "SELECT scope_key FROM research_tasks WHERE id=%s", (lease.task_id,)
                    )
                ).fetchone()
                await self.ledger.release_hold_locked(conn, lease, task["scope_key"])
            await conn.execute(
                "UPDATE research_dependencies SET active=false "
                "WHERE objective_id=%s AND parent_id=%s",
                (lease.objective_id, lease.task_id),
            )
            for child in deps:
                exists = await (
                    await conn.execute(
                        "SELECT 1 FROM research_tasks WHERE objective_id=%s AND id=%s",
                        (lease.objective_id, child),
                    )
                ).fetchone()
                if not exists or child == lease.task_id:
                    raise AccountingError("Dependency must be another task in this objective")
                # Include historical dependency and parent edges: no ancestor/cross-branch cycles.
                cycle = await (
                    await conn.execute(
                        """WITH RECURSIVE edges(parent,child) AS (
                        SELECT parent_id,child_id FROM research_dependencies WHERE objective_id=%s
                        UNION SELECT parent_id,id FROM research_tasks
                        WHERE objective_id=%s AND parent_id IS NOT NULL),
                        reachable(id) AS (SELECT %s::uuid UNION
                        SELECT e.child FROM edges e JOIN reachable r ON e.parent=r.id)
                        SELECT 1 FROM reachable WHERE id=%s""",
                        (lease.objective_id, lease.objective_id, child, lease.task_id),
                    )
                ).fetchone()
                if cycle:
                    raise AccountingError("Dependency would create a cycle")
                await conn.execute(
                    """INSERT INTO research_dependencies(objective_id,parent_id,child_id)
                    VALUES(%s,%s,%s) ON CONFLICT(objective_id,parent_id,child_id)
                    DO UPDATE SET active=true""",
                    (lease.objective_id, lease.task_id, child),
                )
            await conn.execute(
                """INSERT INTO research_task_transitions(objective_id,task_id,attempt_id,
                request_hash,outcome) VALUES(%s,%s,%s,%s,%s)""",
                (lease.objective_id, lease.task_id, lease.attempt_id, request_hash, Jsonb(outcome)),
            )
            await conn.execute(
                """UPDATE research_attempts SET state=%s,settled_at=clock_timestamp()
                WHERE id=%s""",
                (
                    "settled" if state in ("completed", "waiting_children") else state,
                    lease.attempt_id,
                ),
            )
            await conn.execute(
                """UPDATE research_tasks SET state=%s,result=%s,continuation=%s,
                termination_reason=%s,
                lease_owner=NULL,lease_expires_at=NULL,updated_at=clock_timestamp() WHERE id=%s""",
                (
                    state,
                    Jsonb(result) if result is not None else None,
                    Jsonb(continuation or {}),
                    reason,
                    lease.task_id,
                ),
            )
            if state in TERMINAL:
                kind = await (
                    await conn.execute(
                        "SELECT kind FROM research_tasks WHERE id=%s", (lease.task_id,)
                    )
                ).fetchone()
                if kind["kind"] == "research":
                    from .admission import retire_unused

                    await retire_unused(conn, self.ledger, lease)
            # Any fresh terminal child is useful enough to trigger reassessment;
            # all-terminal wakes even if earlier results were already delivered.
            await conn.execute(
                """UPDATE research_tasks p SET state='pending',updated_at=clock_timestamp()
                WHERE p.objective_id=%s AND p.state='waiting_children' AND (
                  EXISTS(SELECT 1 FROM research_dependencies d
                    JOIN research_tasks c ON c.id=d.child_id
                    WHERE d.parent_id=p.id AND d.active AND NOT d.delivered AND c.state=ANY(%s))
                  OR NOT EXISTS(SELECT 1 FROM research_dependencies d
                    JOIN research_tasks c ON c.id=d.child_id
                    WHERE d.parent_id=p.id AND d.active AND NOT(c.state=ANY(%s))))""",
                (lease.objective_id, list(TERMINAL), list(TERMINAL)),
            )
            await conn.execute(
                """UPDATE app_runs SET status=CASE WHEN EXISTS(
                SELECT 1 FROM research_tasks WHERE objective_id=%s
                AND state IN ('running','finalizing'))
                THEN 'running' ELSE 'waiting' END WHERE id=%s""",
                (lease.objective_id, objective["run_id"]),
            )
            if state in TERMINAL and self.terminal_commit:
                await self.terminal_commit(conn, lease, objective, outcome)
            return outcome

    async def get(self, task_id):
        async with self.pool.connection() as conn:
            return await (
                await conn.execute("SELECT * FROM research_tasks WHERE id=%s", (task_id,))
            ).fetchone()
