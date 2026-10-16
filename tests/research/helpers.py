from uuid import uuid4

from comtech.research.accounting import Accounting, Resources
from comtech.research.contracts import SourceScope
from comtech.research.ledger import Lease, Ledger
from comtech.research.registry import JobRegistry


def graph_config(ctx, run):
    return {
        "recursion_limit": 200,
        "configurable": {
            "app_run_id": str(run["id"]),
            "thread_id": str(run["thread_id"]),
            "objective_id": str(ctx.lease.objective_id),
        },
    }


async def accounting_context(pool, profile=None):
    registry = JobRegistry(pool)
    run, _ = await registry.submit(
        thread_id=uuid4(),
        idempotency_key="test",
        message="Synthetic budget test",
        scope=SourceScope(
            scope_ref="test",
            sources=[],
            datasets={},
            fields={},
            capabilities=[],
            pinned_versions={},
        ),
        budget_profile=profile or {},
    )
    objective = await registry.objective(run["id"])
    owner, attempt = uuid4(), uuid4()
    async with pool.connection() as conn:
        task = await (
            await conn.execute(
                """UPDATE research_tasks SET state='running',fence=1,lease_owner=%s,
            lease_expires_at=now()+interval '30 minutes' WHERE objective_id=%s RETURNING id""",
                (owner, objective["id"]),
            )
        ).fetchone()
        await conn.execute(
            """INSERT INTO research_attempts(id,objective_id,task_id,fence,owner,state)
            VALUES(%s,%s,%s,1,%s,'running')""",
            (attempt, objective["id"], task["id"], owner),
        )
    return Accounting(
        Ledger(pool), Lease(objective["id"], task["id"], attempt, owner, 1), Resources()
    ), run
