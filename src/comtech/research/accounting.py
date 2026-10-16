"""Trusted per-run accounting context, bound by the future durable scheduler.

Legacy stream calls have no context and preserve their original behavior. The
same context follows async branches; it never lives in model-authored arguments.
"""

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from openai import APIConnectionError, InternalServerError, RateLimitError

from comtech.agents.budget import digest, serialized
from comtech.agents.errors import InvalidModelOutput

from .budgets import worker_reserve
from .ledger import AccountingError, Lease, Ledger
from .replay import CallReplay, SavedTransient

CURRENT = ContextVar("research_accounting", default=None)
TRANSIENT = (APIConnectionError, InternalServerError, RateLimitError)


class Resources:
    """One instance per API process. Slots stay owned until external work settles."""

    def __init__(self):
        self.gates = {
            "model": asyncio.Semaphore(4),
            "data": asyncio.Semaphore(4),
            "source": asyncio.Semaphore(4),
            "python": asyncio.Semaphore(1),
        }
        self.inflight = set()
        self.owners = {}

    async def drain(self):
        while self.inflight:
            await asyncio.shield(asyncio.gather(*tuple(self.inflight), return_exceptions=True))

    async def drain_attempt(self, attempt_id):
        while pending := [t for t, owner in self.owners.items() if owner == attempt_id]:
            await asyncio.shield(asyncio.gather(*pending, return_exceptions=True))


@dataclass(frozen=True)
class Accounting:
    ledger: Ledger
    lease: Lease
    resources: Resources
    scope: str = "supervisor"

    async def call(
        self,
        kind,
        requested,
        operation,
        measure,
        *,
        phase="exploration",
        replay_key=None,
        encode=None,
        decode=None,
    ):
        objective = await self.ledger.check(self.lease, phase)
        replay = CallReplay(self.ledger)
        entry = None
        if replay_key:
            entry, cached = await replay.prepare(self.lease, replay_key, phase)
            if cached:
                await replay.reconcile_receipt(entry)
                await self.ledger.check(self.lease, "finalization")
                return decode(entry["record"]["output"])

        async def owned():
            async with self.resources.gates[kind]:
                reservation = await self.ledger.reserve(
                    self.lease,
                    str(uuid4()),
                    requested,
                    scope=self.scope,
                    phase=phase,
                )
                try:
                    if entry:
                        await replay.attach(entry, reservation)
                    await self.ledger.start(self.lease, reservation)
                except BaseException:
                    await self.ledger.release(self.lease, reservation)
                    raise
                try:
                    result = await operation()
                except BaseException as error:
                    # Dispatch happened: unsuccessful calls still consume requests/steps.
                    known = {
                        k: v
                        for k, v in requested.items()
                        if k.endswith("requests")
                        or k
                        in ("retries", "control_steps", "supervisor_steps", "python_executions")
                    }
                    known.update(
                        {
                            k: 0
                            for k in requested
                            if k
                            in (
                                "rows",
                                "bytes",
                                "documents_discovered",
                                "documents_opened",
                            )
                        }
                    )
                    if entry and not isinstance(error, asyncio.CancelledError):
                        await replay.save(
                            entry,
                            reservation,
                            known,
                            None,
                            success=False,
                            retryable=isinstance(error, TRANSIENT),
                            invalid_output=str(error)[:1000]
                            if isinstance(error, InvalidModelOutput)
                            else None,
                        )
                    await self.ledger.settle(reservation, known)
                    raise
                actual, documents = measure(result)
                if entry:
                    await replay.save(entry, reservation, actual, documents, output=encode(result))
                await self.ledger.settle(reservation, actual, documents=documents)
                # Reject late output, but never lose incurred usage on stale/cancelled work.
                await self.ledger.check(self.lease, "finalization")
                return result

        task = asyncio.create_task(owned())
        self.resources.inflight.add(task)
        self.resources.owners[task] = self.lease.attempt_id

        def settled(finished):
            self.resources.inflight.discard(finished)
            self.resources.owners.pop(finished, None)
            if not finished.cancelled():
                finished.exception()  # Retrieve detached failure after caller cancellation.

        task.add_done_callback(settled)
        # Deadline/caller cancellation ends waiting, not resource ownership. The
        # adapter's own timeout bounds I/O; even a thread-backed read retains its
        # slot until it really returns. A late result is settled and discarded.
        remaining = max(0, (objective["deadline"] - datetime.now(UTC)).total_seconds())
        async with asyncio.timeout(remaining):
            return await asyncio.shield(task)


@contextmanager
def bind(accounting):
    token = CURRENT.set(accounting)
    try:
        yield accounting
    finally:
        CURRENT.reset(token)


async def admit_worker(task_id, limits):
    context = CURRENT.get()
    if context:
        await context.ledger.protect(
            context.lease,
            "worker:" + task_id,
            worker_reserve(limits),
            charge={"specialist_calls": 1},
        )


@contextmanager
def worker_scope(task_id):
    context = CURRENT.get()
    with bind(replace(context, scope="worker:" + task_id) if context else None):
        yield CURRENT.get()


async def generate(model, role, payload, schema, maximum, *, final=False):
    context = CURRENT.get()
    if not context:
        return await model.generate(role, payload, schema, maximum)
    phase = (
        "finalization" if final or role in ("worker_finalize", "review", "final") else "exploration"
    )
    estimate = model.input_size(role, payload, schema) + maximum
    identity = (
        model.replay_identity(role, payload)
        if hasattr(model, "replay_identity")
        else type(model).__name__
    )
    for attempt in range(2):
        requested = {"model_tokens": estimate, "model_requests": 1, "control_steps": 1}
        if role == "supervisor":
            requested["supervisor_steps"] = 1
        if attempt:
            requested["retries"] = 1

        def measure(result, requested=requested):
            usage = result[1]
            actual = dict(requested)
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            if tokens:
                actual["model_tokens"] = tokens
            else:
                actual.pop("model_tokens")  # Absent usage is never a zero-cost refund.
            return actual, None

        try:
            return await context.call(
                "model",
                requested,
                lambda: model.generate(role, payload, schema, maximum),
                measure,
                phase=phase,
                replay_key=digest(
                    serialized(
                        [
                            context.scope,
                            role,
                            payload,
                            schema.model_json_schema(),
                            maximum,
                            attempt,
                            identity,
                        ]
                    )
                ),
                encode=lambda result: [result[0].model_dump(mode="json"), result[1]],
                decode=lambda stored: (schema.model_validate(stored[0]), stored[1]),
            )
        except (*TRANSIENT, SavedTransient) as error:
            if attempt:
                # Prevent the graph retry policy from multiplying this accounted retry loop.
                raise AccountingError("Model retry limit reached") from error
            await asyncio.sleep(0.5)


async def data_call(name, arguments, operation, *, retry=False, cycle=None):
    context = CURRENT.get()
    if not context:
        return await operation()
    # Transport results are capped at the adapter; serialized output is bounded again here.
    maximum_rows = 100
    requested = {"data_requests": 1, "control_steps": 1, "bytes": 128 * 1024, "rows": maximum_rows}
    if name == "knowledge_search":
        requested["documents_discovered"] = 12
    elif name == "read_document_sections":
        requested["documents_opened"] = 1
    if retry:
        requested["retries"] = 1

    def measure(result):
        import json

        actual = {**requested, "bytes": len(serialized(result).encode("utf-8")), "rows": 0}
        for observation in result.observations:
            # MCP list payloads are an exact JSON object; count delivered records,
            # not just the one envelope observation holding that list.
            try:
                value = json.loads(observation.content)
            except (ValueError, TypeError):
                value = None
            items = value.get("items") if isinstance(value, dict) else None
            actual["rows"] += len(items) if isinstance(items, list) else 1
        documents = {}
        for metric in ("documents_discovered", "documents_opened"):
            if metric in requested:
                refs = {
                    serialized([o.source_ref.source_id, o.source_ref.version])
                    for o in result.observations
                    if o.source_ref.source_type == "document"
                }
                actual[metric] = len(refs)
                documents[metric] = refs
        return actual, documents

    from comtech.agents.contracts import ReadDocumentSectionsResult, ToolResult

    return await context.call(
        "data",
        requested,
        operation,
        measure,
        replay_key=digest(serialized([context.scope, name, arguments, cycle]))
        if cycle is not None
        else None,
        encode=lambda result: {
            "read": isinstance(result, ReadDocumentSectionsResult),
            "value": result.model_dump(mode="json"),
        },
        decode=lambda stored: (
            ReadDocumentSectionsResult if stored["read"] else ToolResult
        ).model_validate(stored["value"]),
    )


async def source_call(operation):
    context = CURRENT.get()
    if not context:
        return await operation()
    return await context.call(
        "source",
        {"source_requests": 1},
        operation,
        lambda _: ({"source_requests": 1}, None),
    )


async def embed(operation, estimated_tokens):
    context = CURRENT.get()
    if not context:
        return await operation()

    def measure(result):
        actual = {"embedding_requests": 1}
        usage = getattr(result, "usage", None)
        if usage is not None:
            actual["embedding_tokens"] = usage.total_tokens
        return actual, None

    return await context.call(
        "model",
        {"embedding_requests": 1, "embedding_tokens": estimated_tokens},
        operation,
        measure,
    )
