import asyncio
import json
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from comtech.research.broker_schema import MIGRATION as BROKER_MIGRATION
from comtech.research.budgets import MIGRATION as BUDGET_MIGRATION
from comtech.research.delivery import MIGRATION as DELIVERY_MIGRATION
from comtech.research.operations import MIGRATION as OPERATIONS_MIGRATION
from comtech.research.queue_schema import MIGRATION as QUEUE_MIGRATION
from comtech.research.schema import MIGRATION as RESEARCH_MIGRATION

# Application tables are separate from the LangGraph-owned schema.
MIGRATIONS = [
    (
        1,
        """
CREATE TABLE IF NOT EXISTS app_runs (
    id uuid PRIMARY KEY,
    thread_id uuid NOT NULL,
    request_id uuid NOT NULL,
    trace_id uuid NOT NULL,
    parent_run_id uuid REFERENCES app_runs(id),
    checkpoint_id text,
    status text NOT NULL CHECK (status IN ('running','completed','failed','interrupted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS app_runs_thread ON app_runs(thread_id, created_at);
CREATE TABLE IF NOT EXISTS app_run_events (
    run_id uuid NOT NULL REFERENCES app_runs(id),
    sequence bigint NOT NULL,
    schema_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL,
    PRIMARY KEY (run_id, sequence)
);
""",
    ),
    (2, "ALTER TABLE app_runs ADD COLUMN IF NOT EXISTS otel_trace_id text;"),
    (3, RESEARCH_MIGRATION),
    (4, BUDGET_MIGRATION),
    (5, QUEUE_MIGRATION),
    (6, DELIVERY_MIGRATION),
    (7, BROKER_MIGRATION),
    (8, OPERATIONS_MIGRATION),
]


@asynccontextmanager
async def database(url):
    async with AsyncConnectionPool(
        url,
        open=False,
        min_size=1,
        max_size=6,
        timeout=5,
        kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 3},
    ) as pool:
        await pool.wait(timeout=30)
        yield pool


async def migrate(pool):
    async with pool.connection() as conn, conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(72610301)")
        await conn.execute("""CREATE TABLE IF NOT EXISTS app_schema_versions (
            version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())""")
        for version, sql in MIGRATIONS:
            existing = await (
                await conn.execute("SELECT 1 FROM app_schema_versions WHERE version=%s", (version,))
            ).fetchone()
            if not existing:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO app_schema_versions(version) VALUES (%s)", (version,)
                )


class Store:
    def __init__(self, pool):
        self.pool = pool

    async def create_run(
        self,
        run_id,
        thread_id,
        request_id,
        trace_id,
        parent=None,
        checkpoint=None,
        graph_run_id=None,
        graph_version=None,
    ):
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO app_runs
                (id,thread_id,request_id,trace_id,parent_run_id,checkpoint_id,status,
                 graph_run_id,graph_version)
                VALUES (%s,%s,%s,%s,%s,%s,'running',%s,%s)""",
                (
                    run_id,
                    thread_id,
                    request_id,
                    trace_id,
                    parent,
                    checkpoint,
                    graph_run_id,
                    graph_version,
                ),
            )

    async def set_otel_trace(self, run_id, trace_id):
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE app_runs SET otel_trace_id=%s WHERE id=%s", (trace_id, run_id)
            )

    async def append(self, run_id, sequence, event, terminal_status=None):
        payload = json.loads(event.model_dump_json(by_alias=True, exclude_none=True))
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO app_run_events(run_id,sequence,payload) VALUES (%s,%s,%s)",
                (run_id, sequence, Jsonb(payload)),
            )
            if terminal_status:
                await conn.execute(
                    "UPDATE app_runs SET status=%s,finished_at=now() WHERE id=%s",
                    (terminal_status, run_id),
                )
        return payload

    async def finish(self, run_id, status):
        async with self.pool.connection() as conn:
            await conn.execute(
                """UPDATE app_runs SET status=%s,finished_at=now()
                WHERE id=%s AND status='running'""",
                (status, run_id),
            )

    async def reconcile(self):
        # Caller holds a process-lifetime advisory lock: no other runner is active.
        async with self.pool.connection() as conn:
            await conn.execute("""UPDATE app_runs SET status='interrupted',finished_at=now()
                WHERE status='running' AND execution_mode='stream'""")

    async def get_run(self, run_id):
        async with self.pool.connection() as conn:
            return await (
                await conn.execute("SELECT * FROM app_runs WHERE id=%s", (run_id,))
            ).fetchone()

    async def list_runs(self, thread_id):
        async with self.pool.connection() as conn:
            return await (
                await conn.execute(
                    "SELECT * FROM app_runs WHERE thread_id=%s ORDER BY created_at DESC LIMIT 100",
                    (thread_id,),
                )
            ).fetchall()

    async def events(self, run_id, after=0):
        # Page reads avoid an unbounded replay buffer or holding a connection while sending.
        while True:
            async with self.pool.connection() as conn:
                rows = await (
                    await conn.execute(
                        """SELECT sequence,payload FROM app_run_events
                    WHERE run_id=%s AND sequence>%s ORDER BY sequence LIMIT 100""",
                        (run_id, after),
                    )
                ).fetchall()
            for row in rows:
                after = row["sequence"]
                yield row
            if len(rows) < 100:
                break
            await asyncio.sleep(0)
