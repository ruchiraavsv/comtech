"""Singleton-owned queue consumers; handlers perform one bounded continuation.

Instantiate inside the API ownership lock. No handlers are registered by default:
HTTP delivery and actual Research admission are separate implementation phases.
"""

import asyncio
from dataclasses import dataclass, field
from uuid import uuid4

from .accounting import Accounting, Resources, bind
from .ledger import RunClosed
from .queue import TaskQueue


@dataclass(frozen=True)
class Outcome:
    state: str = "completed"
    result: dict | None = None
    dependencies: tuple = ()
    continuation: dict = field(default_factory=dict)
    reason: str | None = None


class Scheduler:
    def __init__(
        self,
        pool,
        handlers,
        *,
        resources=None,
        queue=None,
        poll_seconds=0.25,
        control=None,
        activity=None,
    ):
        self.queue = queue or TaskQueue(pool)
        self.resources = resources or Resources()
        self.handlers = dict(handlers)
        self.owner = uuid4()
        self.poll_seconds = poll_seconds
        self.task = None
        self.failure = None
        self.control = control
        self.activity = activity
        self.active = {}

    def cancel_objective(self, objective_id):
        for task, lease in tuple(self.active.items()):
            if lease.objective_id == objective_id:
                task.cancel()

    async def __aenter__(self):
        if self.handlers:
            self.task = asyncio.create_task(self._run(), name="research-scheduler")
            self.task.add_done_callback(self._finished)
        return self

    def _finished(self, task):
        if not task.cancelled():
            self.failure = task.exception()

    def check_health(self):
        if self.failure or (self.task and self.task.done()):
            raise RuntimeError("Background scheduler stopped") from self.failure

    async def __aexit__(self, *args):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            finally:
                # Keep API ownership and adapters alive until detached I/O has settled.
                await self.resources.drain()

    async def _run(self):
        async with asyncio.TaskGroup() as group:
            if self.control:
                group.create_task(self._sweep())
            for _ in range(self.queue.max_runs * self.queue.per_run):
                group.create_task(self._consume())

    async def _consume(self):
        while True:
            claim = await self.queue.claim(self.owner, self.handlers)
            if claim is None:
                await asyncio.sleep(self.poll_seconds)
                continue
            await self._execute(claim)

    async def _execute(self, claim):
        context = Accounting(
            self.queue.ledger, claim.lease, self.resources, claim.task["scope_key"]
        )
        work = asyncio.create_task(self._handle(claim, context))
        self.active[work] = claim.lease
        heartbeat = asyncio.create_task(self._heartbeat(claim.lease))
        try:
            done, _ = await asyncio.wait((work, heartbeat), return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in done:
                # Lease loss, cancellation or a database outage stops semantic work.
                await heartbeat
            outcome = await work
            await self.queue.transition(
                claim.lease,
                state=outcome.state,
                result=outcome.result,
                dependencies=outcome.dependencies,
                continuation=outcome.continuation,
                reason=outcome.reason,
            )
        except RunClosed:
            # Do not requeue stale/expired work or synthesize a terminal answer.
            # R2.5 owns cancellation/expiration and restart reconciliation.
            pass
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
        finally:
            work.cancel()
            heartbeat.cancel()
            await asyncio.gather(work, heartbeat, return_exceptions=True)
            self.active.pop(work, None)

    async def _handle(self, claim, context):
        with bind(context):
            try:
                if self.activity:
                    await self.activity(claim, "started")
                outcome = await self.handlers[claim.task["kind"]](claim)
                if not isinstance(outcome, Outcome):
                    raise TypeError("Task handler must return an Outcome")
            except RunClosed:
                raise
            except Exception as error:
                # Execution status only; no fabricated semantic result or source absence.
                outcome = Outcome(state="failed", reason=type(error).__name__)
            await self.resources.drain_attempt(claim.lease.attempt_id)
            if self.activity:
                await self.activity(claim, "finished", outcome)
            return outcome

    async def _heartbeat(self, lease):
        while True:
            await asyncio.sleep(self.queue.lease_seconds / 3)
            await self.queue.heartbeat(lease)

    async def _sweep(self):
        while True:
            await self.control.sweep()
            await asyncio.sleep(0.5)
