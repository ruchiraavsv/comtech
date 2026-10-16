"""Trusted management operations. None of these are callable through the data SDK."""

import secrets
from dataclasses import dataclass
from datetime import timedelta

from psycopg.types.json import Jsonb

from comtech.agents.budget import digest

from .accounting import Accounting
from .broker_contracts import OPERATIONS, BrokerError
from .contracts import SourceScope
from .ledger import Lease, Ledger


def subset(child, parent):
    """Reject widening rather than silently claiming a broader scope was honored."""
    for name in ("sources", "capabilities"):
        if not set(getattr(child, name)) <= set(getattr(parent, name)):
            raise BrokerError("SCOPE_DENIED", f"Expanded {name}")
    for name in ("datasets", "fields"):
        for key, values in getattr(child, name).items():
            if not set(values) <= set(getattr(parent, name).get(key, [])):
                raise BrokerError("SCOPE_DENIED", f"Expanded {name}")
    for name in ("document_ids", "record_ids"):
        c, p = getattr(child, name), getattr(parent, name)
        if p is not None and (c is None or not set(c) <= set(p)):
            raise BrokerError("SCOPE_DENIED", f"Expanded {name}")
    for key, version in child.pinned_versions.items():
        if parent.pinned_versions.get(key) != version:
            raise BrokerError("SOURCE_VERSION", "Changed pinned source")
    if any(key not in child.pinned_versions for key in child.sources):
        raise BrokerError("SOURCE_VERSION", "Source is not pinned")
    if child.document_version_policy != parent.document_version_policy:
        raise BrokerError("SCOPE_DENIED", "Changed version policy")
    if parent.time_start and (child.time_start is None or child.time_start < parent.time_start):
        raise BrokerError("SCOPE_DENIED", "Expanded time interval")
    if parent.time_end and (child.time_end is None or child.time_end > parent.time_end):
        raise BrokerError("SCOPE_DENIED", "Expanded time interval")
    if child.time_start and child.time_end and child.time_start > child.time_end:
        raise BrokerError("INVALID_ARGUMENT", "Invalid time interval")


@dataclass(frozen=True)
class Access:
    context: Accounting
    scope: SourceScope
    execution_id: object | None
    token_hash: str


class Capabilities:
    def __init__(self, pool, resources):
        self.pool, self.resources, self.ledger = pool, resources, Ledger(pool)

    async def register_scope(self, lease, scope):
        scope = SourceScope.model_validate(scope).model_copy(deep=True)
        if scope.sources != ["documents"] or not set(scope.capabilities) <= set(OPERATIONS):
            raise BrokerError("CAPABILITY_UNAVAILABLE", "Research supports documents only")
        if scope.record_ids is not None:
            raise BrokerError("CAPABILITY_UNAVAILABLE", "Use document scope for this adapter")
        async with self.pool.connection() as conn, conn.transaction():
            objective = await self.ledger._active(conn, lease, "exploration")
            task = await (
                await conn.execute(
                    "SELECT parent_id FROM research_tasks WHERE id=%s", (lease.task_id,)
                )
            ).fetchone()
            parent = None
            if task["parent_id"]:
                parent = await (
                    await conn.execute(
                        "SELECT s.scope,t.kind FROM research_tasks t "
                        "LEFT JOIN research_data_scopes s "
                        "ON s.task_id=t.id WHERE t.id=%s",
                        (task["parent_id"],),
                    )
                ).fetchone()
                if parent["kind"] == "research" and not parent["scope"]:
                    raise BrokerError("SCOPE_DENIED", "Parent scope is not registered")
            inherited = parent["scope"] if parent and parent["scope"] else objective["scope"]
            subset(scope, SourceScope.model_validate(inherited))
            old = await (
                await conn.execute(
                    "SELECT scope FROM research_data_scopes WHERE task_id=%s", (lease.task_id,)
                )
            ).fetchone()
            value = scope.model_dump(mode="json")
            if old and old["scope"] != value:
                raise BrokerError("SCOPE_DENIED", "Registered scope is immutable")
            if not old:
                await conn.execute(
                    "INSERT INTO research_data_scopes VALUES(%s,%s,%s)",
                    (lease.task_id, lease.objective_id, Jsonb(value)),
                )
        return scope

    async def issue(self, lease, *, execution_id=None, seconds=120):
        if not 0 < seconds <= 120:
            raise ValueError("Capability lifetime must be at most 120 seconds")
        token = secrets.token_urlsafe(32)
        async with self.pool.connection() as conn, conn.transaction():
            objective = await self.ledger._active(conn, lease, "exploration")
            if execution_id:
                valid = await (
                    await conn.execute(
                        "SELECT 1 FROM research_executions WHERE id=%s AND attempt_id=%s "
                        "AND state='running'",
                        (execution_id, lease.attempt_id),
                    )
                ).fetchone()
                if not valid:
                    raise BrokerError("INVALID_CAPABILITY", "Execution is not active")
            await conn.execute(
                "INSERT INTO research_data_capabilities "
                "(token_hash,objective_id,task_id,attempt_id,execution_id,expires_at) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    digest(token),
                    lease.objective_id,
                    lease.task_id,
                    lease.attempt_id,
                    execution_id,
                    min(objective["deadline"], objective["now"] + timedelta(seconds=seconds)),
                ),
            )
        return token

    async def resolve(self, token, operation):
        if not isinstance(token, str) or len(token) > 100:
            raise BrokerError("INVALID_CAPABILITY", "Invalid execution capability")
        async with self.pool.connection() as conn, conn.transaction():
            row = await (
                await conn.execute(
                    """SELECT c.*,s.scope,a.owner,a.fence,t.scope_key
                FROM research_data_capabilities c JOIN research_data_scopes s ON s.task_id=c.task_id
                JOIN research_attempts a ON a.id=c.attempt_id
                JOIN research_tasks t ON t.id=c.task_id
                    WHERE token_hash=%s""",
                    (digest(token),),
                )
            ).fetchone()
            if not row:
                raise BrokerError("INVALID_CAPABILITY", "Expired or unknown execution capability")
            lease = Lease(
                row["objective_id"], row["task_id"], row["attempt_id"], row["owner"], row["fence"]
            )
            objective = await self.ledger._active(conn, lease, "exploration")
            if row["revoked"] or row["expires_at"] <= objective["now"]:
                raise BrokerError("INVALID_CAPABILITY", "Expired or unknown execution capability")
            if row["execution_id"]:
                active = await (
                    await conn.execute(
                        "SELECT 1 FROM research_executions WHERE id=%s AND attempt_id=%s "
                        "AND state='running'",
                        (row["execution_id"], row["attempt_id"]),
                    )
                ).fetchone()
                if not active:
                    raise BrokerError("INVALID_CAPABILITY", "Execution ended")
            scope = SourceScope.model_validate(row["scope"])
            if operation not in OPERATIONS:
                raise BrokerError("CAPABILITY_UNAVAILABLE", "Operation unavailable for Research")
            if operation not in scope.capabilities:
                raise BrokerError("SCOPE_DENIED", "Operation outside assigned scope")
        return Access(
            Accounting(self.ledger, lease, self.resources, row["scope_key"]),
            scope,
            row["execution_id"],
            row["token_hash"],
        )

    async def revoke(self, token):
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE research_data_capabilities SET revoked=true WHERE token_hash=%s",
                (digest(token),),
            )
