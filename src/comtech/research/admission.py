"""Atomic logical recursion, inherited scopes and dependency identities."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from comtech.agents.budget import digest, serialized

from .access import subset
from .actions import PROMPT_VERSION, ResearchLimits
from .broker_contracts import OPERATIONS
from .contracts import SourceScope
from .ledger import BudgetExhausted
from .queue import bounded


class Admission:
    def __init__(self, queue, limits=None):
        self.queue, self.limits = queue, limits or ResearchLimits()

    async def propose(self, lease, proposals):
        """All proposals, scope grants and edges commit together, including replay."""
        async with self.queue.pool.connection() as conn, conn.transaction():
            objective = await self.queue.ledger._active(conn, lease, "exploration")
            parent = await (
                await conn.execute(
                    "SELECT t.*,s.scope FROM research_tasks t LEFT JOIN research_data_scopes s "
                    "ON s.task_id=t.id WHERE t.id=%s",
                    (lease.task_id,),
                )
            ).fetchone()
            depth = parent["input"].get("depth", -1) + 1
            if depth > self.limits.max_depth:
                raise BudgetExhausted("depth_limit")
            scope = SourceScope.model_validate(parent["scope"] or objective["scope"])
            tasks = []
            for proposal in proposals:
                child_scope = proposal.narrowed_scope
                subset(child_scope, scope)
                if (
                    child_scope.sources != ["documents"]
                    or child_scope.record_ids is not None
                    or not set(child_scope.capabilities) <= set(OPERATIONS)
                ):
                    raise ValueError("Research supports document capabilities only")
                # Scope labels/advisory prose cannot manufacture fresh analysis identities.
                key = "research:" + digest(
                    serialized(
                        [
                            PROMPT_VERSION,
                            proposal.description.strip(),
                            proposal.expected_output.strip(),
                            proposal.analysis_mode,
                            child_scope.model_dump(mode="json", exclude={"scope_ref"}),
                            sorted(set(proposal.input_refs)),
                            proposal.partition.strip(),
                        ]
                    )
                )
                old = await (
                    await conn.execute(
                        "SELECT * FROM research_tasks WHERE objective_id=%s AND logical_key=%s",
                        (lease.objective_id, key),
                    )
                ).fetchone()
                task_id = old["id"] if old else uuid4()
                if old:
                    cycle = await (
                        await conn.execute(
                            """WITH RECURSIVE edges(parent,child) AS (
                        SELECT parent_id,child_id FROM research_dependencies WHERE objective_id=%s
                        UNION SELECT parent_id,id FROM research_tasks
                        WHERE objective_id=%s AND parent_id IS NOT NULL), reachable(id) AS (
                        SELECT %s::uuid UNION SELECT e.child FROM edges e JOIN reachable r
                        ON e.parent=r.id) SELECT 1 FROM reachable WHERE id=%s""",
                            (lease.objective_id, lease.objective_id, task_id, lease.task_id),
                        )
                    ).fetchone()
                    if cycle:
                        raise ValueError("Recursive proposal creates a dependency cycle")
                count = await (
                    await conn.execute(
                        "SELECT count(*) AS n FROM research_dependencies WHERE parent_id=%s "
                        "AND child_id<>%s",
                        (lease.task_id, task_id),
                    )
                ).fetchone()
                if parent["kind"] == "research" and count["n"] >= self.limits.max_children:
                    raise ValueError("Cumulative child limit reached")

                # Validate and collect the complete input closure before creating a task.
                granted, visiting = {}, set()

                async def visit(ref, visiting=visiting, granted=granted, child_scope=child_scope):
                    if ref in visiting:
                        raise ValueError("Cyclic input closure")
                    if ref in granted:
                        return
                    visiting.add(ref)
                    row = await (
                        await conn.execute(
                            "SELECT r.* FROM research_data_records r "
                            "LEFT JOIN research_data_grants g "
                            "ON g.ref=r.ref AND g.task_id=%s WHERE r.ref=%s AND r.objective_id=%s "
                            "AND (r.task_id=%s OR g.task_id IS NOT NULL)",
                            (lease.task_id, ref, lease.objective_id, lease.task_id),
                        )
                    ).fetchone()
                    if (
                        not row
                        or row["expired"]
                        or digest(serialized(row["payload"])) != row["content_hash"]
                    ):
                        raise ValueError(
                            "Missing, ungranted or changed input. input_refs accepts only "
                            "durable registered references available to this task. Use [] for "
                            "fresh research and put document IDs in the document scope."
                        )
                    required = SourceScope.model_validate(row["source_scope"])
                    required.capabilities = []
                    subset(required, child_scope)
                    for child in row["input_refs"]:
                        await visit(child)
                    visiting.remove(ref)
                    granted[ref] = row

                for ref in proposal.input_refs:
                    await visit(ref)
                if not old:
                    scope_key = "task:" + str(task_id)
                    charge = {"research_tasks": 1}
                    if parent["kind"] == "supervisor":
                        charge["specialist_calls"] = 1
                    await self.queue.ledger.protect_locked(
                        conn,
                        lease,
                        scope_key,
                        self.limits.reserve(),
                        charge,
                    )
                    payload = bounded(
                        {
                            **proposal.model_dump(mode="json"),
                            "depth": depth,
                            "prompt_version": PROMPT_VERSION,
                        }
                    )
                    await conn.execute(
                        "INSERT INTO research_tasks "
                        "(id,objective_id,parent_id,logical_key,kind,input,"
                        "admission_hash,scope_key) "
                        "VALUES(%s,%s,%s,%s,'research',%s,%s,%s)",
                        (
                            task_id,
                            lease.objective_id,
                            lease.task_id,
                            key,
                            Jsonb(payload),
                            key,
                            scope_key,
                        ),
                    )
                    await conn.execute(
                        "INSERT INTO research_data_scopes VALUES(%s,%s,%s)",
                        (task_id, lease.objective_id, Jsonb(child_scope.model_dump(mode="json"))),
                    )
                for ref in granted:
                    await conn.execute(
                        "INSERT INTO research_data_grants VALUES(%s,%s) ON CONFLICT DO NOTHING",
                        (ref, task_id),
                    )
                await conn.execute(
                    "INSERT INTO research_dependencies(objective_id,parent_id,child_id) "
                    "VALUES(%s,%s,%s) ON CONFLICT(objective_id,parent_id,child_id) "
                    "DO UPDATE SET active=true",
                    (lease.objective_id, lease.task_id, task_id),
                )
                tasks.append(task_id)
            return tuple(dict.fromkeys(tasks))


async def retire_unused(conn, ledger, lease):
    """Called under the objective lock when a Research task becomes terminal.

    Historical edges stay for cycle detection. Shared live dependencies protect work.
    In-flight usage is still settled by its owner; stale output cannot commit.
    """
    pending = [lease.task_id]
    while pending:
        parent = pending.pop()
        children = await (
            await conn.execute(
                "SELECT child_id FROM research_dependencies WHERE parent_id=%s",
                (parent,),
            )
        ).fetchall()
        await conn.execute(
            "UPDATE research_dependencies SET active=false WHERE parent_id=%s", (parent,)
        )
        for item in children:
            child = await (
                await conn.execute(
                    "SELECT t.* FROM research_tasks t WHERE t.id=%s "
                    "AND t.state NOT IN ('completed','failed','cancelled') AND NOT EXISTS("
                    "SELECT 1 FROM research_dependencies d "
                    "JOIN research_tasks p ON p.id=d.parent_id "
                    "WHERE d.child_id=t.id AND d.active "
                    "AND p.state NOT IN ('completed','failed','cancelled'))",
                    (item["child_id"],),
                )
            ).fetchone()
            if not child:
                continue
            await conn.execute(
                "UPDATE research_tasks SET state='cancelled',termination_reason='unneeded',"
                "lease_owner=NULL,lease_expires_at=NULL,updated_at=clock_timestamp() WHERE id=%s",
                (child["id"],),
            )
            await conn.execute(
                "UPDATE research_attempts SET state='cancelled',settled_at=clock_timestamp() "
                "WHERE task_id=%s AND state='running'",
                (child["id"],),
            )
            await conn.execute(
                "UPDATE research_data_capabilities SET revoked=true WHERE task_id=%s",
                (child["id"],),
            )
            await ledger.release_hold_locked(conn, lease, child["scope_key"])
            pending.append(child["id"])
