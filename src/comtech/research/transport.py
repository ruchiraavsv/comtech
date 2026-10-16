"""Private service transport. No credentials or management handles enter generated code."""

from dataclasses import asdict
from uuid import UUID

import httpx
from pydantic import Field

from comtech.agents.contracts import Contract

from .accounting import Accounting
from .contracts import SourceScope
from .ledger import AccountingError, BudgetExhausted, Lease, Ledger, RunClosed


class LeaseInput(Contract):
    objective_id: UUID
    task_id: UUID
    attempt_id: UUID
    owner: UUID
    fence: int = Field(ge=1)


async def context_for(pool, resources, value, phase="exploration"):
    lease = Lease(**LeaseInput.model_validate(value).model_dump())
    ledger = Ledger(pool)
    await ledger.check(lease, phase)
    async with pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT t.scope_key,s.scope FROM research_tasks t LEFT JOIN research_data_scopes s "
                "ON s.task_id=t.id WHERE t.id=%s AND t.objective_id=%s",
                (lease.task_id, lease.objective_id),
            )
        ).fetchone()
    if not row or not row["scope"]:
        raise RunClosed("Task has no registered document scope")
    return Accounting(ledger, lease, resources, row["scope_key"]), SourceScope.model_validate(
        row["scope"]
    )


def lease_json(context):
    return {k: str(v) if isinstance(v, UUID) else v for k, v in asdict(context.lease).items()}


class PrivateClient:
    def __init__(self, url, secret, *, client=None):
        self.client = client or httpx.AsyncClient(
            base_url=url.rstrip("/"), timeout=140, headers={"Authorization": "Bearer " + secret}
        )

    async def call(self, path, body=None, *, maximum=64 * 1024 * 1024):
        try:
            async with self.client.stream(
                "GET" if body is None else "POST", path, json=body
            ) as reply:
                raw = bytearray()
                async for chunk in reply.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > maximum:
                        raise AccountingError("Private service response exceeded its bound")
                import json

                value = json.loads(raw)
                if reply.status_code >= 400:
                    code = value.get("code")
                    if code == "budget":
                        raise BudgetExhausted(value.get("reason", "objective_budget"))
                    if code == "closed":
                        raise RunClosed("Private operation lease is closed")
                    raise AccountingError("Private service rejected the operation")
                return value
        except (httpx.HTTPError, ValueError) as error:
            raise AccountingError("Private service unavailable; no direct fallback") from error

    async def close(self):
        await self.client.aclose()
