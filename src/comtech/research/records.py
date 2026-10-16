"""Durable immutable evidence/coverage references, explicit inheritance and opaque cursors."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from comtech.agents.budget import digest, serialized

from .access import subset
from .broker_contracts import BrokerError
from .contracts import SourceScope


class Records:
    def __init__(self, capabilities):
        self.capabilities, self.pool = capabilities, capabilities.pool

    async def put(self, access, kind, payload, coverage, *, inputs=(), ref=None, scope=None):
        lease = access.context.lease
        ref = ref or "REF-" + uuid4().hex
        scope = scope or access.scope
        value_hash = digest(serialized(payload))
        async with self.pool.connection() as conn, conn.transaction():
            await access.context.ledger._active(conn, lease, "finalization")
            old = await (
                await conn.execute("SELECT * FROM research_data_records WHERE ref=%s", (ref,))
            ).fetchone()
            if old:
                if (
                    old["task_id"] != lease.task_id
                    or old["content_hash"] != value_hash
                    or old["kind"] != kind
                    or old["input_refs"] != list(inputs)
                ):
                    raise BrokerError("INVALID_REFERENCE", "Immutable reference changed")
                return ref
            await conn.execute(
                """INSERT INTO research_data_records
                (ref,objective_id,task_id,execution_id,kind,payload,content_hash,source_scope,
                 coverage,input_refs) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    ref,
                    lease.objective_id,
                    lease.task_id,
                    access.execution_id,
                    kind,
                    Jsonb(payload),
                    value_hash,
                    Jsonb(scope.model_dump(mode="json")),
                    Jsonb(coverage),
                    Jsonb(list(inputs)),
                ),
            )
        return ref

    async def get(self, access, ref, *, kinds=None):
        lease = access.context.lease
        async with self.pool.connection() as conn, conn.transaction():
            objective = await access.context.ledger._active(conn, lease, "finalization")
            row = await (
                await conn.execute(
                    """SELECT r.*,g.task_id AS granted FROM research_data_records r
                LEFT JOIN research_data_grants g ON g.ref=r.ref AND g.task_id=%s
                WHERE r.ref=%s AND r.objective_id=%s""",
                    (lease.task_id, ref, lease.objective_id),
                )
            ).fetchone()
            if not row or (row["task_id"] != lease.task_id and not row["granted"]):
                raise BrokerError("INVALID_REFERENCE", "Unknown or ungranted reference")
            if row["expired"]:
                raise BrokerError("ARTIFACT_EXPIRED", "Stored reference has expired")
            if kinds and row["kind"] not in kinds:
                raise BrokerError("INVALID_REFERENCE", "Reference type mismatch")
            # Active runs pin their inputs beyond nominal retention expiry.
            if row["expires_at"] <= objective["now"] and objective["status"] not in (
                "queued",
                "running",
                "waiting",
            ):
                raise BrokerError("ARTIFACT_EXPIRED", "Stored reference has expired")
            required = SourceScope.model_validate(row["source_scope"])
            # Reading a result needs its data scope, not the producer's tool privileges.
            required.capabilities = []
            subset(required, access.scope)
            if digest(serialized(row["payload"])) != row["content_hash"]:
                raise BrokerError("HASH_MISMATCH", "Stored reference hash mismatch")
            return row

    async def grant(self, lease, ref, recipient_task):
        """Trusted orchestration only; source scope is checked even for siblings."""
        async with self.pool.connection() as conn, conn.transaction():
            await self.capabilities.ledger._active(conn, lease, "finalization")
            recipient = await (
                await conn.execute(
                    "SELECT scope FROM research_data_scopes WHERE task_id=%s AND objective_id=%s",
                    (recipient_task, lease.objective_id),
                )
            ).fetchone()
            if not recipient:
                raise BrokerError("INVALID_REFERENCE", "Cannot grant this reference")
            seen, visiting = set(), set()

            async def visit(key):
                if key in visiting:
                    raise BrokerError("INVALID_REFERENCE", "Cyclic input lineage")
                if key in seen:
                    return
                visiting.add(key)
                row = await (
                    await conn.execute(
                        "SELECT * FROM research_data_records WHERE ref=%s AND objective_id=%s",
                        (key, lease.objective_id),
                    )
                ).fetchone()
                if not row or row["expired"]:
                    raise BrokerError("INVALID_REFERENCE", "Cannot grant missing or expired input")
                if digest(serialized(row["payload"])) != row["content_hash"]:
                    raise BrokerError("HASH_MISMATCH", "Input lineage hash mismatch")
                required = SourceScope.model_validate(row["source_scope"])
                required.capabilities = []
                subset(required, SourceScope.model_validate(recipient["scope"]))
                for child in row["input_refs"]:
                    await visit(child)
                await conn.execute(
                    "INSERT INTO research_data_grants VALUES(%s,%s) ON CONFLICT DO NOTHING",
                    (key, recipient_task),
                )
                visiting.remove(key)
                seen.add(key)

            await visit(ref)

    async def offset(self, access, operation, request, cursor):
        if cursor is None:
            return 0
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT * FROM research_data_cursors WHERE token=%s AND task_id=%s",
                    (cursor, access.context.lease.task_id),
                )
            ).fetchone()
        if not row or row["request_hash"] != digest(serialized([operation, request])):
            raise BrokerError("INVALID_CURSOR", "Cursor does not match this task/query")
        return row["offset_value"]

    async def cursor(self, access, operation, request, offset):
        token = "CUR-" + uuid4().hex
        async with self.pool.connection() as conn, conn.transaction():
            lease = access.context.lease
            await access.context.ledger._active(conn, lease, "finalization")
            await conn.execute(
                "INSERT INTO research_data_cursors VALUES(%s,%s,%s,%s,%s)",
                (
                    token,
                    lease.objective_id,
                    lease.task_id,
                    digest(serialized([operation, request])),
                    offset,
                ),
            )
        return token
