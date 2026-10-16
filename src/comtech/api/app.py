import asyncio
import hmac
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import anyio
from ag_ui.core import RunErrorEvent, RunFinishedEvent, TextMessageContentEvent
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langsmith import Client, tracing_context
from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse
from starlette.background import BackgroundTask

from comtech.db import Store, database
from comtech.events import graph_events, sse_record
from comtech.graph import build_graph
from comtech.logging import configure_logging
from comtech.observability import Observability
from comtech.research.accounting import Resources, bind
from comtech.research.background import BackgroundGraph
from comtech.research.broker_contracts import DOCUMENT_FIELDS, OPERATIONS
from comtech.research.contracts import SourceScope
from comtech.research.control import Control
from comtech.research.delivery import Delivery
from comtech.research.ledger import BudgetExhausted, RunClosed
from comtech.research.operations import Activity, Maintenance, progress
from comtech.research.queue import TaskQueue
from comtech.research.registry import (
    ActiveRunError,
    JobRegistry,
    SubmissionConflict,
    validate_checkpoint_identity,
)
from comtech.research.scheduler import Scheduler
from comtech.research.transport import LeaseInput, context_for
from comtech.settings import Settings

log = logging.getLogger("comtech")


class RunInput(BaseModel):
    thread_id: UUID = Field(default_factory=uuid4)
    message: str = Field(min_length=1, max_length=4000)
    execution_mode: Literal["stream", "background"] = "stream"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class ResumeInput(BaseModel):
    checkpoint_id: str = Field(min_length=1, max_length=200)


class EmbeddingInput(BaseModel):
    model_config = {"extra": "forbid"}
    lease: LeaseInput
    query: str = Field(min_length=1, max_length=1000)


def create_app(settings: Settings | None = None):
    @asynccontextmanager
    async def lifespan(app):
        cfg = settings or Settings()
        url = cfg.require_database()
        async with AsyncExitStack() as stack:
            logging_runtime = configure_logging(cfg)
            stack.push_async_callback(asyncio.to_thread, logging_runtime.close)
            observation = Observability(cfg)
            stack.push_async_callback(asyncio.to_thread, observation.close)
            app.state.observation = observation
            pool = await stack.enter_async_context(database(url))
            # Enforce the single-runner assumption even across overlapping deployments.
            async with await AsyncConnection.connect(url, autocommit=True) as lease:
                acquired = await (
                    await lease.execute("SELECT pg_try_advisory_lock(72610302)")
                ).fetchone()
                if not acquired[0]:
                    raise RuntimeError(
                        "Another API runner is active; stop it before starting this one"
                    )
                app.state.settings = cfg
                app.state.pool = pool
                app.state.store = Store(pool)
                checkpointer = AsyncPostgresSaver(pool)
                delivery = Delivery(pool)
                queue = TaskQueue(pool, terminal_commit=delivery.terminal_locked)
                resources = Resources()
                if cfg.research_enabled:
                    # Partition four aggregate data/source slots across API and broker.
                    resources.gates["data"] = asyncio.Semaphore(2)
                    resources.gates["source"] = asyncio.Semaphore(2)
                app.state.resources = resources
                if cfg.agent_mode == "enterprise":
                    from comtech.agents.runtime import enterprise_runtime

                    app.state.graph = await stack.enter_async_context(
                        enterprise_runtime(
                            cfg,
                            checkpointer,
                            **(
                                {"pool": pool, "resources": resources, "queue": queue}
                                if cfg.research_enabled
                                else {}
                            ),
                        )
                    )
                else:
                    app.state.graph = build_graph(checkpointer, cfg.mock_delay_seconds)
                app.state.active = {}
                app.state.tracer = None
                if cfg.tracing_mode == "langsmith":
                    app.state.tracer = Client(
                        api_key=cfg.langsmith_api_key.get_secret_value(),
                        api_url=cfg.langsmith_endpoint,
                        workspace_id=cfg.langsmith_workspace_id or None,
                        tracing_sampling_rate=cfg.langsmith_tracing_sampling_rate,
                        timeout_ms=3000,
                        hide_inputs=cfg.trace_hide_inputs or cfg.research_enabled,
                        hide_outputs=cfg.trace_hide_outputs or cfg.research_enabled,
                        tracing_error_callback=lambda error: log.warning(
                            "trace_upload_failed", extra={"error_type": type(error).__name__}
                        ),
                    )
                await app.state.store.reconcile()
                app.state.jobs = JobRegistry(pool)
                app.state.control = Control(pool, delivery)
                from comtech.mcp.models import SNAPSHOT_ID

                pins = {"documents": cfg.agent_build_id, "northstar": SNAPSHOT_ID}
                if cfg.background_enabled:
                    await app.state.control.recover(pins)
                specialist = getattr(app.state.graph, "research_specialist", None)
                handlers = (
                    {"supervisor": BackgroundGraph(app.state.graph, delivery, pins, specialist)}
                    if cfg.background_enabled
                    else {}
                )
                if cfg.research_enabled:
                    handlers["research"] = app.state.graph.research_agent

                def traced(handler):
                    async def execute(claim):
                        context = {
                            "thread_id": str(claim.objective["thread_id"]),
                            "run_id": str(claim.objective["run_id"]),
                            "task_id": str(claim.lease.task_id),
                            "attempt_id": str(claim.lease.attempt_id),
                            "route": claim.task["kind"],
                        }
                        with (
                            tracing_context(
                                enabled=cfg.tracing_mode == "langsmith",
                                client=app.state.tracer,
                                project_name=cfg.langsmith_project,
                            ),
                            observation.execution(context),
                        ):
                            return await handler(claim)

                    return execute

                handlers = {name: traced(handler) for name, handler in handlers.items()}
                if cfg.background_enabled:
                    await stack.enter_async_context(
                        Maintenance(
                            pool,
                            checkpointer,
                            getattr(app.state.graph, "research_broker", None),
                            cfg.research_maintenance_seconds,
                        )
                    )
                app.state.scheduler = Scheduler(
                    pool,
                    handlers,
                    queue=queue,
                    control=app.state.control,
                    resources=resources,
                    activity=Activity(delivery),
                )
                log.info("application_ready")
                try:
                    async with app.state.scheduler:
                        yield
                finally:
                    if app.state.tracer:
                        await asyncio.to_thread(app.state.tracer.flush)
                        await asyncio.to_thread(app.state.tracer.close)

    app = FastAPI(title="Comtech infrastructure", lifespan=lifespan)

    @app.middleware("http")
    async def internal_boundary(request, call_next):
        if request.url.path == "/internal/research/embed":
            cfg = app.state.settings
            if not cfg.research_enabled:
                return JSONResponse({"code": "disabled"}, status_code=404)
            expected = "Bearer " + cfg.research_service_token.get_secret_value()
            if not hmac.compare_digest(request.headers.get("authorization", ""), expected):
                return JSONResponse({"code": "unauthorized"}, status_code=401)
            length = request.headers.get("content-length", "")
            if not length.isdecimal() or int(length) > 8192:
                return JSONResponse({"code": "body_limit"}, status_code=413)
        return await call_next(request)

    @app.get("/health/live")
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready():
        try:
            app.state.scheduler.check_health()
            if app.state.settings.research_enabled:
                await app.state.graph.research_broker.ready(app.state.settings.agent_build_id)
            async with app.state.pool.connection() as conn:
                await conn.execute("SELECT 1 FROM app_schema_versions LIMIT 1")
        except Exception as error:
            log.warning("readiness_failed", extra={"error_type": type(error).__name__})
            raise HTTPException(503, "A required execution service is unavailable") from None
        return {
            "status": "ready",
            "mode": app.state.settings.agent_mode,
            "tracing": app.state.settings.tracing_mode != "off",
            "observability_mode": app.state.settings.tracing_mode,
            "background_enabled": app.state.settings.background_enabled,
            "research_enabled": app.state.settings.research_enabled,
        }

    @app.post("/internal/research/embed")
    async def embed(body: EmbeddingInput, authorization: str | None = Header(default=None)):
        cfg = app.state.settings
        if not cfg.research_enabled:
            raise HTTPException(404)
        expected = "Bearer " + cfg.research_service_token.get_secret_value()
        if not hmac.compare_digest(authorization or "", expected):
            raise HTTPException(401)
        try:
            context, scope = await context_for(
                app.state.pool, app.state.resources, body.lease.model_dump()
            )
            if scope.pinned_versions.get("documents") != cfg.agent_build_id:
                raise ValueError("Embedding release mismatch")
            with bind(context):
                vector = await app.state.graph.query_embedding(body.query)
            return {"vector": vector}
        except (BudgetExhausted, RunClosed) as error:
            return JSONResponse(
                {
                    "code": "budget" if isinstance(error, BudgetExhausted) else "closed",
                    "reason": getattr(error, "reason", "closed"),
                },
                status_code=409,
            )
        except Exception:
            raise HTTPException(409, "Embedding operation is unavailable for this lease") from None

    async def start(thread_id, inputs, checkpoint=None, parent=None):
        if thread_id in app.state.active:
            raise HTTPException(409, "A run is already active in this conversation")
        run_id, request_id, trace_id = uuid4(), uuid4(), uuid4()
        app.state.active[thread_id] = run_id
        cfg = app.state.settings
        context = {
            "run_id": str(run_id),
            "request_id": str(request_id),
            "thread_id": str(thread_id),
            "trace_id": str(trace_id),
        }
        config = {
            "configurable": {"thread_id": str(thread_id), "app_run_id": str(run_id)},
            "run_id": trace_id,
            "run_name": f"{cfg.agent_mode}_conversation",
            "metadata": {**context, "environment": cfg.app_env, "git_revision": cfg.git_revision},
            "tags": [cfg.app_env, cfg.agent_mode],
            "recursion_limit": 200,
        }
        try:
            graph_run_id = run_id if cfg.agent_mode == "enterprise" else None
            graph_version = 2 if cfg.agent_mode == "enterprise" else None
            if checkpoint:
                config["configurable"]["checkpoint_id"] = checkpoint
                snapshot = await app.state.graph.aget_state(config)
                if not snapshot.created_at or not snapshot.next:
                    raise HTTPException(400, "Checkpoint is missing or has no pending nodes")
                if snapshot.values.get("objective_id"):
                    raise HTTPException(
                        409, "Background checkpoints require canonical job recovery"
                    )
                graph_run_id = snapshot.values.get("run_id")
                graph_version = snapshot.values.get("graph_version", 1)
            await app.state.store.create_run(
                run_id,
                thread_id,
                request_id,
                trace_id,
                parent,
                checkpoint,
                graph_run_id=graph_run_id,
                graph_version=graph_version,
            )
        except UniqueViolation as error:
            app.state.active.pop(thread_id, None)
            if error.diag.constraint_name == "app_runs_one_active_thread":
                raise HTTPException(409, "A run is already active in this conversation") from None
            raise
        except BaseException:
            app.state.active.pop(thread_id, None)
            raise

        async def cleanup():
            # Idempotent fallback also covers disconnection before iteration starts.
            with anyio.CancelScope(shield=True):
                try:
                    with anyio.move_on_after(5):
                        await app.state.store.finish(run_id, "interrupted")
                except Exception as error:
                    log.error(
                        "run_cleanup_failed", extra={**context, "error_type": type(error).__name__}
                    )
                finally:
                    if app.state.active.get(thread_id) == run_id:
                        app.state.active.pop(thread_id, None)

        async def execution_events():
            sequence = 0
            output = ""
            log.info("run_started", extra=context)
            try:
                with tracing_context(
                    enabled=cfg.tracing_mode == "langsmith",
                    client=app.state.tracer,
                    project_name=cfg.langsmith_project,
                ):
                    async with asyncio.timeout(cfg.request_timeout_seconds):
                        async for event in graph_events(
                            app.state.graph, inputs, config, run_id, thread_id
                        ):
                            if isinstance(event, TextMessageContentEvent):
                                output = (output + event.delta)[:16000]
                            sequence += 1
                            terminal = "completed" if isinstance(event, RunFinishedEvent) else None
                            payload = await app.state.store.append(
                                run_id, sequence, event, terminal
                            )
                            yield sse_record(run_id, sequence, payload)
                app.state.observation.output(output)
                app.state.observation.outcome("completed")
                log.info("run_completed", extra=context)
            except asyncio.CancelledError:
                app.state.observation.outcome("interrupted")
                log.info("run_interrupted", extra=context)
                raise
            except Exception as error:
                app.state.observation.outcome("failed")
                log.error("run_failed", extra={**context, "error_type": type(error).__name__})
                event = RunErrorEvent(
                    message="Run timed out"
                    if isinstance(error, TimeoutError)
                    else "Assistant run failed; no approved answer is available",
                    code="TIMEOUT" if isinstance(error, TimeoutError) else "EXECUTION_FAILED",
                )
                try:
                    # If a prior append had an ambiguous result, do not invent replay guarantees.
                    sequence += 1
                    payload = await app.state.store.append(run_id, sequence, event, "failed")
                    yield sse_record(run_id, sequence, payload)
                except Exception as persistence_error:
                    log.error(
                        "terminal_event_unavailable",
                        extra={**context, "error_type": type(persistence_error).__name__},
                    )
            finally:
                await cleanup()

        async def stream():
            try:
                with app.state.observation.execution(context, parent, inputs) as span:
                    if span:
                        span_context = span.get_span_context()
                        await app.state.store.set_otel_trace(
                            run_id, format(span_context.trace_id, "032x")
                        )
                    async for record in execution_events():
                        yield record
            finally:
                await cleanup()

        return EventSourceResponse(
            stream(),
            ping=10,
            send_timeout=15,
            headers={
                "X-Run-ID": str(run_id),
                "X-Thread-ID": str(thread_id),
                "X-Request-ID": str(request_id),
                "X-Trace-ID": str(trace_id),
            },
            background=BackgroundTask(cleanup),
        )

    @app.post("/api/runs")
    async def run(body: RunInput):
        if not body.message.strip():
            raise HTTPException(422, "Message cannot be blank")
        if body.execution_mode == "background":
            cfg = app.state.settings
            if not cfg.background_enabled:
                raise HTTPException(409, "Background execution is disabled")
            if not body.idempotency_key:
                raise HTTPException(422, "Background submission requires an idempotency key")
            app.state.scheduler.check_health()
            from comtech.mcp.models import SNAPSHOT_ID

            scope = SourceScope(
                scope_ref="published-knowledge",
                sources=["documents", "northstar"],
                datasets={"documents": ["documents"]},
                fields={"documents": [*DOCUMENT_FIELDS, "content"]},
                capabilities=[*OPERATIONS, "lookup"],
                pinned_versions={"documents": cfg.agent_build_id, "northstar": SNAPSHOT_ID},
            )
            try:
                stored, _ = await app.state.jobs.submit(
                    thread_id=body.thread_id,
                    idempotency_key=body.idempotency_key,
                    message=body.message,
                    scope=scope,
                    budget_profile={},
                    duration_seconds=cfg.objective_timeout_seconds,
                    finalization_seconds=cfg.objective_finalization_seconds,
                )
            except (ActiveRunError, SubmissionConflict) as error:
                raise HTTPException(409, str(error)) from None
            return JSONResponse(jsonable_encoder(public_run(stored)), status_code=202)
        return await start(body.thread_id, {"messages": [HumanMessage(content=body.message)]})

    def public_run(row):
        if row["execution_mode"] != "background":
            return row
        return {
            **{
                k: row[k]
                for k in (
                    "id",
                    "thread_id",
                    "status",
                    "execution_mode",
                    "created_at",
                    "finished_at",
                    "terminal_reason",
                )
            },
            "run_id": row["id"],
            "result_available": row["result"] is not None and not expired(row),
            "result_expired": expired(row),
            "message": row["input"].get("message", ""),
            "events_url": f"/api/runs/{row['id']}/events?follow=true",
            "result_url": f"/api/runs/{row['id']}/result",
        }

    def expired(row):
        return row.get("result_expired", False) or bool(
            row.get("result_expires_at") and row["result_expires_at"] <= datetime.now(UTC)
        )

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: UUID):
        result = await app.state.store.get_run(run_id)
        if not result:
            raise HTTPException(404, "Run not found")
        return {**public_run(result), "progress": await progress(app.state.pool, run_id)}

    @app.get("/api/runs/{run_id}/result")
    async def result(run_id: UUID):
        row = await app.state.store.get_run(run_id)
        if not row:
            raise HTTPException(404, "Run not found")
        if row["execution_mode"] != "background":
            raise HTTPException(409, "Legacy results are available through event replay")
        if expired(row):
            raise HTTPException(410, "Stored result has expired")
        if row["result"] is None:
            return JSONResponse(
                {"status": row["status"], "result_available": False},
                status_code=409 if row["status"] in ("failed", "cancelled") else 202,
            )
        return row["result"]

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: UUID):
        row = await app.state.store.get_run(run_id)
        if not row:
            raise HTTPException(404, "Run not found")
        if row["execution_mode"] != "background":
            raise HTTPException(409, "Explicit cancellation applies to background runs")
        objective_id = await app.state.control.cancel(run_id)
        app.state.scheduler.cancel_objective(objective_id)
        return public_run(await app.state.store.get_run(run_id))

    @app.get("/api/threads/{thread_id}/runs")
    async def runs(thread_id: UUID):
        return [public_run(row) for row in await app.state.store.list_runs(thread_id)]

    @app.get("/api/threads/{thread_id}/checkpoints")
    async def checkpoints(thread_id: UUID):
        config = {"configurable": {"thread_id": str(thread_id)}}
        return [
            {
                "checkpoint_id": item.config["configurable"]["checkpoint_id"],
                "created_at": item.created_at,
                "next": item.next,
                "messages": [
                    {"role": m.type, "content": m.content} for m in item.values.get("messages", [])
                ],
            }
            async for item in app.state.graph.aget_state_history(config, limit=30)
        ]

    @app.post("/api/runs/{run_id}/resume")
    async def resume(run_id: UUID, body: ResumeInput):
        parent = await get_run(run_id)
        if parent["execution_mode"] == "background":
            if not app.state.settings.background_enabled or parent["status"] not in (
                "queued",
                "running",
                "waiting",
            ):
                raise HTTPException(409, "This background run cannot be resumed")
            stored = await app.state.store.get_run(run_id)
            objective = await JobRegistry(app.state.pool).objective(run_id)
            snapshot = await app.state.graph.aget_state(
                {"configurable": {"thread_id": str(stored["thread_id"])}}
            )
            try:
                validate_checkpoint_identity(snapshot, stored, objective["id"])
                if snapshot.config["configurable"].get("checkpoint_id") != body.checkpoint_id:
                    raise ValueError("Checkpoint is not the current continuation")
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
            # Startup recovery and the durable queue own execution. Repeated client
            # requests only acknowledge the existing continuation; never fork it.
            return JSONResponse(jsonable_encoder(public_run(stored)), status_code=202)
        return await start(parent["thread_id"], None, body.checkpoint_id, run_id)

    @app.get("/api/runs/{run_id}/events")
    async def replay(
        run_id: UUID,
        after: int = Query(default=0, ge=0),
        follow: bool = False,
        last_event_id: str | None = Header(default=None),
    ):
        state = await get_run(run_id)
        if state.get("result_expired"):
            raise HTTPException(410, "Saved output has expired")
        if last_event_id:
            try:
                cursor_run, cursor_sequence = last_event_id.rsplit(":", 1)
                if UUID(cursor_run) != run_id or int(cursor_sequence) < 0:
                    raise ValueError
                after = max(after, int(cursor_sequence))
            except ValueError:
                raise HTTPException(400, "Invalid event cursor for this run") from None

        async def records():
            cursor = after
            try:
                async with asyncio.timeout(app.state.settings.event_follow_seconds):
                    while True:
                        async for item in app.state.store.events(run_id, cursor):
                            cursor = item["sequence"]
                            yield sse_record(run_id, cursor, item["payload"])
                        if not follow:
                            return
                        row = await app.state.store.get_run(run_id)
                        if (
                            row["status"] in ("completed", "failed", "cancelled", "interrupted")
                            and cursor >= row["event_sequence"]
                        ):
                            return
                        await asyncio.sleep(0.1)
            except TimeoutError:
                return  # Connection lifetime does not own execution.

        return EventSourceResponse(records(), ping=10, send_timeout=15)

    return app


app = create_app()
