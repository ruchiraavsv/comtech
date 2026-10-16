"""Durable, fenced Python attempts and replay over the accepted broker/accounting boundary."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

from comtech.agents.budget import digest, serialized

from .access import Access
from .broker_contracts import BrokerError
from .contracts import SourceScope
from .ledger import AccountingError, BudgetExhausted
from .runner_wire import DEFAULT_LIMITS, job_request


class PythonExecutor:
    def __init__(self, broker, runner, environment_digest):
        self.broker, self.runner = broker, runner
        self.environment_digest = environment_digest
        self.pool = broker.capabilities.pool

    async def prune(self):
        """Trusted maintenance hook; preserve manifests/outputs while expiring logs and code."""
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE research_executions SET record=(record - 'logs') || "
                "'{\"logs_expired\":true}'::jsonb WHERE record->>'kind'='python' "
                "AND record ? 'logs' AND (record->>'logs_expires_at')::double precision "
                "<extract(epoch from clock_timestamp())"
            )
            await conn.execute(
                "UPDATE research_executions e SET record=(e.record - 'code') || "
                "'{\"code_expired\":true}'::jsonb FROM research_objectives o,app_runs r "
                "WHERE e.objective_id=o.id AND o.run_id=r.id "
                "AND r.status IN ('completed','failed','cancelled') "
                "AND e.record->>'kind'='python' AND e.record ? 'code' "
                "AND e.created_at<clock_timestamp()-interval '7 days'"
            )

    async def execute(
        self,
        context,
        code,
        purpose,
        input_refs,
        *,
        request_id,
        limits=None,
        analysis_provenance=None,
    ):
        if not isinstance(purpose, str) or not 1 <= len(purpose) <= 1000:
            raise ValueError("Bounded execution purpose required")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 200:
            raise ValueError("Bounded execution identity required")
        requested_limits = dict(DEFAULT_LIMITS if limits is None else limits)
        job_request(
            {
                "execution_id": str(uuid4()),
                "code": code,
                "input_refs": input_refs,
                "limits": requested_limits,
                "environment_digest": self.environment_digest,
            }
        )
        lease = context.lease
        async with self.pool.connection() as conn, conn.transaction():
            objective = await context.ledger._active(conn, lease, "exploration")
            registered = await (
                await conn.execute(
                    "SELECT scope FROM research_data_scopes WHERE task_id=%s", (lease.task_id,)
                )
            ).fetchone()
            if not registered:
                raise BrokerError("SCOPE_DENIED", "Task document scope is not registered")
            scope = SourceScope.model_validate(registered["scope"])
        self.broker.documents.eligible(scope)
        access = Access(context, scope, None, "")
        for ref in input_refs:
            await self.broker.records.get(access, ref)
        identity = digest(
            serialized(
                [
                    code,
                    purpose,
                    input_refs,
                    requested_limits,
                    self.environment_digest,
                    scope.model_dump(mode="json"),
                ]
            )
        )
        operation_key = "python-execution:" + request_id
        record = {
            "kind": "python",
            "code": code,
            "code_hash": digest(code),
            "purpose": purpose,
            "input_refs": input_refs,
            "environment_digest": self.environment_digest,
            "limits": requested_limits,
            "pinned_versions": scope.pinned_versions,
        }
        if analysis_provenance is not None:
            # Supplied by orchestration, never Python or model-authored tool arguments.
            if any(
                not isinstance(k, str) or not isinstance(v, str)
                for k, v in analysis_provenance.items()
            ):
                raise ValueError("Analysis provenance must contain string fields")
            record["analysis_provenance"] = dict(analysis_provenance)
            identity = digest(serialized([identity, analysis_provenance]))
        async with self.pool.connection() as conn, conn.transaction():
            await context.ledger._active(conn, lease, "exploration")
            entry = await (
                await conn.execute(
                    "SELECT * FROM research_executions WHERE task_id=%s AND operation_key=%s",
                    (lease.task_id, operation_key),
                )
            ).fetchone()
            if entry:
                if entry["request_hash"] != identity:
                    raise ValueError("Python request identity is immutable")
            else:
                entry = await (
                    await conn.execute(
                        "INSERT INTO research_executions "
                        "(id,objective_id,task_id,attempt_id,operation_key,"
                        "request_hash,state,record) "
                        "VALUES(%s,%s,%s,%s,%s,%s,'pending',%s) RETURNING *",
                        (
                            uuid4(),
                            lease.objective_id,
                            lease.task_id,
                            lease.attempt_id,
                            operation_key,
                            identity,
                            Jsonb(record),
                        ),
                    )
                ).fetchone()
        cancelled = asyncio.Event()

        async def active():
            if cancelled.is_set():
                raise asyncio.CancelledError()
            await context.ledger.check(lease)

        async def run():
            await active()
            remaining = int((objective["exploration_deadline"] - datetime.now(UTC)).total_seconds())
            if remaining < 1:
                raise BudgetExhausted("deadline")
            effective = {
                **requested_limits,
                "wall_seconds": min(requested_limits["wall_seconds"], remaining),
            }
            async with self.pool.connection() as conn, conn.transaction():
                await context.ledger._active(conn, lease, "exploration")
                record["started_at"] = datetime.now(UTC).isoformat()
                changed = await conn.execute(
                    "UPDATE research_executions SET state='running',attempt_id=%s,record=%s "
                    "WHERE id=%s AND state='pending'",
                    (lease.attempt_id, Jsonb(record), entry["id"]),
                )
                if not changed.rowcount:
                    raise AccountingError("Python outcome requires reconciliation")
                entry["attempt_id"] = lease.attempt_id
            token = await self.broker.capabilities.issue(lease, execution_id=entry["id"])
            receipts = []
            source_receipts, data_errors = [], []

            async def data_call(operation, arguments, sequence):
                try:
                    reply = await self.broker.call(
                        token, operation, arguments, request_id=f"python:{entry['id']}:{sequence}"
                    )
                    if reply["receipt_ref"]:
                        receipts.append(reply["receipt_ref"])
                        if operation in (
                            "describe",
                            "knowledge_search",
                            "read_document_sections",
                            "enumerate_documents",
                            "read_spans",
                        ):
                            source_receipts.append(reply["receipt_ref"])
                except BrokerError as error:
                    reply = {
                        "value": {"error": {"code": error.code, "message": str(error)}},
                        "receipt_ref": None,
                    }
                error = reply["value"].get("error")
                if error:
                    # Preserve trusted broker diagnostics, never arbitrary exception text
                    # or runner-supplied claims about which data operation failed.
                    data_errors.append(
                        {
                            "tool_name": operation,
                            "code": error["code"],
                            "message": error["message"][:500],
                        }
                    )
                    del data_errors[:-5]
                return reply

            try:
                result = await self.runner.execute(
                    {
                        "execution_id": str(entry["id"]),
                        "code": code,
                        "input_refs": input_refs,
                        "limits": effective,
                        "environment_digest": self.environment_digest,
                    },
                    data_call,
                    active,
                )
                if result.get("environment_digest") != self.environment_digest:
                    raise ValueError("Runner environment changed")
                if result.get("execution_id") != str(entry["id"]):
                    raise ValueError("Runner execution identity mismatch")
                # Logs are separate bounded audit fields, never part of the model result.
                logs = {key: result.pop(key, "") for key in ("stdout", "stderr")}
                result.pop("type", None)
                result["receipt_refs"] = (
                    receipts if result["status"] == "success" else source_receipts
                )
                result["data_errors"] = data_errors
                result["input_refs"] = input_refs
                if self.broker.counter.count(result) > 3000:
                    result = {
                        "execution_id": str(entry["id"]),
                        "status": "resource_limit",
                        "error": "result_token_limit",
                        "receipt_refs": list(source_receipts),
                        "data_errors": data_errors,
                        "omitted_receipt_count": 0,
                    }
                    # Discard oversized generated output, not independently registered
                    # source work. Failed-execution artifacts still cannot be selected.
                    while self.broker.counter.count(result) > 3000 and result["receipt_refs"]:
                        result["receipt_refs"].pop(0)
                        result["omitted_receipt_count"] += 1
                    if self.broker.counter.count(result) > 3000:
                        result["data_errors"] = []
                await self.finish(entry, result, logs)
                return result
            except (OSError, EOFError, TimeoutError, ValueError) as error:
                result = {
                    "execution_id": str(entry["id"]),
                    "status": "error",
                    "error": "runner_unavailable"
                    if isinstance(error, OSError)
                    else "runner_protocol",
                }
                await self.finish(entry, result, {})
                return result
            except BaseException:
                await self.finish(entry, {"status": "cancelled", "error": "execution_stopped"}, {})
                raise
            finally:
                await self.broker.capabilities.revoke(token)

        requested = {"python_executions": 1, "control_steps": 1}
        try:
            return await context.call(
                "python",
                requested,
                run,
                lambda _: (requested, None),
                replay_key="python-result:" + str(entry["id"]),
                encode=lambda result: result,
                decode=lambda result: result,
            )
        except BaseException:
            cancelled.set()
            raise

    async def finish(self, entry, result, logs):
        async with self.pool.connection() as conn, conn.transaction():
            await self.broker.capabilities.ledger._lock(conn, entry["objective_id"])
            status = "success" if result["status"] == "success" else "failed"
            await conn.execute(
                "UPDATE research_executions SET state=%s,record=record || %s "
                "WHERE id=%s AND state='running' AND attempt_id=%s",
                (
                    status,
                    Jsonb(
                        {
                            "output": result,
                            "finished_at": datetime.now(UTC).isoformat(),
                            "logs": logs,
                            "logs_expires_at": datetime.now(UTC).timestamp() + 86400,
                        }
                    ),
                    entry["id"],
                    entry["attempt_id"],
                ),
            )
