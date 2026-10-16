import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.errors import ForeignKeyViolation, UniqueViolation

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import Limits
from comtech.agents.graph import build_enterprise_graph, build_legacy_graph
from comtech.db import MIGRATIONS, Store, migrate
from comtech.research import accounting
from comtech.research.contracts import SourceScope
from comtech.research.ledger import AccountingError
from comtech.research.registry import (
    ActiveRunError,
    JobRegistry,
    SubmissionConflict,
    validate_checkpoint_identity,
)
from tests.agents.helpers import FakeModel, FakeTools

from .helpers import accounting_context, graph_config

pytestmark = pytest.mark.integration


def submission(**changes):
    return dict(
        thread_id=uuid4(),
        idempotency_key="submission",
        message="Find the owner",
        scope=SourceScope(
            scope_ref="scope",
            sources=["documents"],
            datasets={},
            fields={},
            capabilities=["search"],
            pinned_versions={"documents": "synthetic-v1"},
        ),
        budget_profile={},
        **changes,
    )


async def test_migration_preserves_legacy_checkpoints_results_and_event_sequence(unmigrated_pool):
    pool = unmigrated_pool
    async with pool.connection() as conn:
        await conn.execute("CREATE TABLE app_schema_versions(version integer PRIMARY KEY)")
        for version, script in MIGRATIONS[:2]:
            await conn.execute(script)
            await conn.execute("INSERT INTO app_schema_versions VALUES(%s)", (version,))
        run, thread = uuid4(), uuid4()
        await conn.execute(
            """INSERT INTO app_runs(id,thread_id,request_id,trace_id,status)
            VALUES(%s,%s,%s,%s,'interrupted')""",
            (run, thread, uuid4(), uuid4()),
        )
        await conn.execute(
            "INSERT INTO app_run_events(run_id,sequence,payload) VALUES(%s,7,'{}')",
            (run,),
        )
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    config = {"configurable": {"thread_id": str(thread)}, "recursion_limit": 200}
    legacy = build_legacy_graph(FakeModel(), FakeTools(), TokenCounter(), Limits(), saver)
    previous = await legacy.ainvoke({"messages": [HumanMessage(content="Owner?")]}, config)
    snapshot = await legacy.aget_state(config)
    await migrate(pool)
    await migrate(pool)  # Migration re-entry does not rewrite historical content.
    stored = await Store(pool).get_run(run)
    assert stored["execution_mode"] == "stream" and stored["event_sequence"] == 7
    assert stored["graph_run_id"] is None and stored["graph_version"] is None
    current = build_enterprise_graph(FakeModel(), FakeTools(), TokenCounter(), Limits(), saver)
    recovered = await current.aget_state(config)
    assert recovered.config == snapshot.config
    assert recovered.values["task_results"] == previous["task_results"]
    assert not recovered.values.get("graph_version")


async def test_racing_identical_submissions_share_run_objective_queue_and_deadlines(research_pool):
    registry, request = JobRegistry(research_pool), submission()
    answers = await asyncio.gather(*(registry.submit(**request) for _ in range(6)))
    assert sum(created for _, created in answers) == 1
    assert len({run["id"] for run, _ in answers}) == 1
    run = answers[0][0]
    original = await registry.objective(run["id"])
    assert run["id"] == run["graph_run_id"] and run["graph_version"] == 2
    retry, created = await registry.submit(**{**request, "duration_seconds": 3600})
    assert not created and retry["id"] == run["id"]
    assert await registry.objective(run["id"]) == original
    async with research_pool.connection() as conn:
        counts = await (
            await conn.execute("SELECT count(*) AS count FROM research_tasks")
        ).fetchone()
        assert counts["count"] == 1
    with pytest.raises(SubmissionConflict):
        await registry.submit(**{**request, "message": "Different question"})


async def test_cross_mode_admission_and_startup_reconciliation(research_pool):
    registry, request = JobRegistry(research_pool), submission()
    run, _ = await registry.submit(**request)
    with pytest.raises(ActiveRunError):
        await registry.submit(**{**request, "idempotency_key": "other"})
    store = Store(research_pool)
    with pytest.raises(UniqueViolation):
        await store.create_run(uuid4(), request["thread_id"], uuid4(), uuid4())
    async with research_pool.connection() as conn:
        await conn.execute("UPDATE app_runs SET status='interrupted' WHERE id=%s", (run["id"],))
    with pytest.raises(ActiveRunError):
        await registry.submit(**{**request, "idempotency_key": "cannot-overtake-recovery"})
    with pytest.raises(UniqueViolation):
        await store.create_run(uuid4(), request["thread_id"], uuid4(), uuid4())
    async with research_pool.connection() as conn:
        await conn.execute("UPDATE app_runs SET status='running' WHERE id=%s", (run["id"],))
    legacy_id = uuid4()
    await store.create_run(legacy_id, uuid4(), uuid4(), uuid4())
    await store.reconcile()
    assert (await store.get_run(run["id"]))["status"] == "running"
    assert (await store.get_run(legacy_id))["status"] == "interrupted"


async def test_terminal_key_stays_idempotent_but_new_request_can_follow(research_pool):
    registry, request = JobRegistry(research_pool), submission()
    first, _ = await registry.submit(**request)
    async with research_pool.connection() as conn:
        await conn.execute("UPDATE app_runs SET status='completed' WHERE id=%s", (first["id"],))
    retry, created = await registry.submit(**request)
    assert retry["id"] == first["id"] and not created
    second, created = await registry.submit(**{**request, "idempotency_key": "next"})
    assert created and second["id"] != first["id"]


async def test_task_parent_cannot_cross_objective_boundary(research_pool):
    registry = JobRegistry(research_pool)
    one, _ = await registry.submit(**submission())
    two, _ = await registry.submit(**submission())
    objective = await registry.objective(two["id"])
    async with research_pool.connection() as conn:
        parent = await (
            await conn.execute(
                """SELECT t.id FROM research_tasks t JOIN research_objectives o
            ON o.id=t.objective_id WHERE o.run_id=%s""",
                (one["id"],),
            )
        ).fetchone()
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(
                """INSERT INTO research_tasks(id,objective_id,parent_id,logical_key,kind,input)
                VALUES(%s,%s,%s,'child','research','{}')""",
                (uuid4(), objective["id"], parent["id"]),
            )


async def test_attempt_execution_and_artifact_identities_cannot_cross_tasks(research_pool):
    registry = JobRegistry(research_pool)
    run, _ = await registry.submit(**submission())
    objective = await registry.objective(run["id"])
    async with research_pool.connection() as conn:
        task = await (
            await conn.execute(
                "SELECT id FROM research_tasks WHERE objective_id=%s",
                (objective["id"],),
            )
        ).fetchone()
        sibling, attempt, execution = uuid4(), uuid4(), uuid4()
        await conn.execute(
            """INSERT INTO research_tasks(id,objective_id,logical_key,kind,input)
            VALUES(%s,%s,'sibling','knowledge_worker','{}')""",
            (sibling, objective["id"]),
        )
        await conn.execute(
            """INSERT INTO research_attempts(id,objective_id,task_id,fence,owner,state)
            VALUES(%s,%s,%s,1,%s,'running')""",
            (attempt, objective["id"], task["id"], uuid4()),
        )
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(
                """INSERT INTO research_reservations
                (id,objective_id,task_id,attempt_id,operation_key,phase,state)
                VALUES(%s,%s,%s,%s,'read','exploration','reserved')""",
                (uuid4(), objective["id"], sibling, attempt),
            )
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(
                """INSERT INTO research_executions
                (id,objective_id,task_id,attempt_id,operation_key,request_hash,state,record)
                VALUES(%s,%s,%s,%s,'operation','hash','pending','{}')""",
                (execution, objective["id"], sibling, attempt),
            )
        await conn.execute(
            """INSERT INTO research_executions
            (id,objective_id,task_id,attempt_id,operation_key,request_hash,state,record)
            VALUES(%s,%s,%s,%s,'operation','hash','pending','{}')""",
            (execution, objective["id"], task["id"], attempt),
        )
        with pytest.raises(ForeignKeyViolation):
            await conn.execute(
                """INSERT INTO research_artifacts
                (id,objective_id,task_id,execution_id,state,record)
                VALUES(%s,%s,%s,%s,'writing','{}')""",
                (uuid4(), objective["id"], sibling, execution),
            )


async def test_graph_uses_canonical_identity_and_checkpoint_validation_rejects_other_run(
    research_pool,
):
    registry = JobRegistry(research_pool)
    ctx, run = await accounting_context(research_pool)
    objective = await registry.objective(run["id"])
    saver = AsyncPostgresSaver(research_pool)
    await saver.setup()
    graph = build_enterprise_graph(FakeModel(), FakeTools(), TokenCounter(), Limits(), saver)
    config = graph_config(ctx, run)
    message = {"messages": [HumanMessage(content="Owner?")]}
    with pytest.raises(AccountingError):
        await graph.ainvoke(message, config)
    with accounting.bind(ctx):
        wrong_config = {
            **config,
            "configurable": {**config["configurable"], "app_run_id": str(uuid4())},
        }
        with pytest.raises(AccountingError):
            await graph.ainvoke(message, wrong_config)
        output = await graph.ainvoke(message, config)
    assert output["run_id"] == str(run["id"])
    assert all(e["run_id"] == str(run["id"]) for e in output["evidence"].values())
    snapshot = await graph.aget_state(config)
    validate_checkpoint_identity(snapshot, run, objective["id"])
    for key, replacement in (
        ("run_id", str(uuid4())),
        ("objective_id", str(uuid4())),
        ("graph_version", 99),
    ):
        wrong = SimpleNamespace(
            config=snapshot.config, values={**snapshot.values, key: replacement}
        )
        with pytest.raises(ValueError, match="canonical"):
            validate_checkpoint_identity(wrong, run, objective["id"])
