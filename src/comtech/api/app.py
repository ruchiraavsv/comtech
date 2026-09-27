import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from uuid import UUID, uuid4

import anyio
from ag_ui.core import RunErrorEvent, RunFinishedEvent, TextMessageContentEvent
from fastapi import FastAPI, Header, HTTPException, Query
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langsmith import Client, tracing_context
from psycopg import AsyncConnection
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse
from starlette.background import BackgroundTask

from comtech.db import Store, database
from comtech.events import graph_events, sse_record
from comtech.graph import build_graph
from comtech.logging import configure_logging
from comtech.observability import Observability
from comtech.settings import Settings

log = logging.getLogger("comtech")


class RunInput(BaseModel):
    thread_id: UUID = Field(default_factory=uuid4)
    message: str = Field(min_length=1, max_length=4000)


class ResumeInput(BaseModel):
    checkpoint_id: str = Field(min_length=1, max_length=200)


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
                app.state.graph = build_graph(AsyncPostgresSaver(pool), cfg.mock_delay_seconds)
                app.state.active = {}
                app.state.tracer = None
                if cfg.tracing_mode == "langsmith":
                    app.state.tracer = Client(
                        api_key=cfg.langsmith_api_key.get_secret_value(),
                        api_url=cfg.langsmith_endpoint,
                        workspace_id=cfg.langsmith_workspace_id or None,
                        tracing_sampling_rate=cfg.langsmith_tracing_sampling_rate,
                        timeout_ms=3000,
                        hide_inputs=cfg.trace_hide_inputs,
                        hide_outputs=cfg.trace_hide_outputs,
                        tracing_error_callback=lambda error: log.warning(
                            "trace_upload_failed", extra={"error_type": type(error).__name__}
                        ),
                    )
                await app.state.store.reconcile()
                log.info("application_ready")
                try:
                    yield
                finally:
                    if app.state.tracer:
                        await asyncio.to_thread(app.state.tracer.flush)
                        await asyncio.to_thread(app.state.tracer.close)

    app = FastAPI(title="Comtech infrastructure", lifespan=lifespan)

    @app.get("/health/live")
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready():
        try:
            async with app.state.pool.connection() as conn:
                await conn.execute("SELECT 1 FROM app_schema_versions LIMIT 1")
        except Exception as error:
            log.warning("readiness_failed", extra={"error_type": type(error).__name__})
            raise HTTPException(503, "Database is unavailable") from None
        return {
            "status": "ready",
            "mode": "mock",
            "tracing": app.state.settings.tracing_mode != "off",
            "observability_mode": app.state.settings.tracing_mode,
        }

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
            "configurable": {"thread_id": str(thread_id)},
            "run_id": trace_id,
            "run_name": "mock_conversation",
            "metadata": {**context, "environment": cfg.app_env, "git_revision": cfg.git_revision},
            "tags": [cfg.app_env, "mock"],
        }
        try:
            if checkpoint:
                config["configurable"]["checkpoint_id"] = checkpoint
                snapshot = await app.state.graph.aget_state(config)
                if not snapshot.created_at or not snapshot.next:
                    raise HTTPException(400, "Checkpoint is missing or has no pending nodes")
            await app.state.store.create_run(
                run_id, thread_id, request_id, trace_id, parent, checkpoint
            )
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
                    else "Mock run failed",
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
        return await start(body.thread_id, {"messages": [HumanMessage(content=body.message)]})

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: UUID):
        result = await app.state.store.get_run(run_id)
        if not result:
            raise HTTPException(404, "Run not found")
        return result

    @app.get("/api/threads/{thread_id}/runs")
    async def runs(thread_id: UUID):
        return await app.state.store.list_runs(thread_id)

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
        return await start(parent["thread_id"], None, body.checkpoint_id, run_id)

    @app.get("/api/runs/{run_id}/events")
    async def replay(
        run_id: UUID,
        after: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None),
    ):
        await get_run(run_id)
        if last_event_id:
            try:
                cursor_run, cursor_sequence = last_event_id.rsplit(":", 1)
                if UUID(cursor_run) != run_id or int(cursor_sequence) < 0:
                    raise ValueError
                after = max(after, int(cursor_sequence))
            except ValueError:
                raise HTTPException(400, "Invalid event cursor for this run") from None

        async def records():
            async for item in app.state.store.events(run_id, after):
                yield sse_record(run_id, item["sequence"], item["payload"])

        return EventSourceResponse(records(), ping=10, send_timeout=15)

    return app


app = create_app()
