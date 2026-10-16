"""Private broker/runner management service; never published as a generated-code API."""

import asyncio
import hmac
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import AsyncConnection
from pydantic import Field

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import Contract, Limits
from comtech.db import database
from comtech.retrieval.search import HybridSearch
from comtech.retrieval.store import SourceStore
from comtech.settings import Settings

from .access import Access, Capabilities
from .accounting import CURRENT, Resources, bind
from .broker import Broker
from .broker_contracts import BrokerError
from .ledger import AccountingError, BudgetExhausted, RunClosed
from .python_execution import PythonExecutor
from .runner_client import RunnerClient
from .transport import LeaseInput, PrivateClient, context_for, lease_json


class DataRequest(Contract):
    token: str = Field(max_length=100)
    operation: str = Field(max_length=60)
    arguments: dict
    request_id: str = Field(max_length=200)


class ArtifactRequest(Contract):
    lease: LeaseInput
    ref: str = Field(max_length=100)


class RetainRequest(Contract):
    lease: LeaseInput
    refs: list[str] = Field(max_length=1000)


class PythonRequest(Contract):
    lease: LeaseInput
    code: str = Field(max_length=65536)
    purpose: str = Field(max_length=1000)
    input_refs: list[str] = Field(max_length=100)
    request_id: str = Field(max_length=200)
    environment_digest: str = Field(min_length=64, max_length=64)
    analysis_provenance: dict[str, str] | None = None


def secure(app, secret):
    if len(secret) < 32:
        raise ValueError("Private Research service requires a secret of at least 32 characters")

    @app.middleware("http")
    async def guard(request, call_next):
        if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + secret):
            return JSONResponse({"code": "unauthorized"}, status_code=401)
        if request.method == "POST":
            length = request.headers.get("content-length", "")
            if not length.isdecimal() or int(length) > 128 * 1024:
                return JSONResponse({"code": "body_limit"}, status_code=413)
        return await call_next(request)


def create_broker_app(settings=None, *, broker=None, executor=None):
    cfg = settings or Settings()
    secret = cfg.research_service_token.get_secret_value()

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            if broker is not None:
                app.state.broker, app.state.executor = broker, executor
            else:
                # This process has no OpenAI key. Query embeddings use one fixed API-owned port.
                if cfg.openai_api_key.get_secret_value():
                    raise ValueError("Model credentials must not enter the broker service")
                pool = await stack.enter_async_context(database(cfg.require_database()))
                lease = await stack.enter_async_context(
                    await AsyncConnection.connect(cfg.require_database(), autocommit=True)
                )
                owned = await (
                    await lease.execute("SELECT pg_try_advisory_lock(72610305)")
                ).fetchone()
                if not owned[0]:
                    raise RuntimeError("Another Research broker is active")
                resources = Resources()
                resources.gates["data"] = asyncio.Semaphore(2)
                resources.gates["source"] = asyncio.Semaphore(2)
                counter = await asyncio.to_thread(TokenCounter, cfg.agent_token_encoding)
                store = await asyncio.to_thread(
                    SourceStore, cfg.ingestion_artifact_root, cfg.agent_build_id
                )
                api = PrivateClient(cfg.research_api_url, secret)
                stack.push_async_callback(api.close)

                async def embed(query):
                    return (
                        await api.call(
                            "/internal/research/embed",
                            {
                                "lease": lease_json(CURRENT.get()),
                                "query": query,
                            },
                            maximum=256 * 1024,
                        )
                    )["vector"]

                search = HybridSearch(store, cfg, None, counter, embed_query=embed)
                stack.push_async_callback(search.close)
                service = Broker(
                    Capabilities(pool, resources),
                    store,
                    search,
                    counter,
                    Limits(
                        max_sections_per_read=cfg.max_sections_per_read,
                        max_tokens_per_section=cfg.max_tokens_per_section,
                        max_tokens_per_read=cfg.max_tokens_per_read,
                    ),
                    cfg.research_artifact_root,
                )
                runner = RunnerClient(cfg.research_runner_socket)
                async with asyncio.timeout(30):
                    while True:
                        try:
                            description = await runner.describe()
                            break
                        except (OSError, EOFError):
                            await asyncio.sleep(0.25)
                app.state.broker = service
                app.state.executor = PythonExecutor(
                    service, runner, description["environment_digest"]
                )
                stack.push_async_callback(resources.drain)
            yield

    app = FastAPI(title="Private Research broker", lifespan=lifespan, docs_url=None, redoc_url=None)
    secure(app, secret)

    @app.exception_handler(AccountingError)
    async def accounting_error(request, error):
        return JSONResponse(
            {
                "code": "budget"
                if isinstance(error, BudgetExhausted)
                else "closed"
                if isinstance(error, RunClosed)
                else "accounting",
                "reason": getattr(error, "reason", "accounting_failure"),
            },
            status_code=409,
        )

    @app.exception_handler(BrokerError)
    async def broker_error(request, error):
        return JSONResponse({"code": error.code}, status_code=400)

    async def access(value, phase="finalization"):
        service = app.state.broker
        context, scope = await context_for(
            service.capabilities.pool, service.capabilities.resources, value.model_dump(), phase
        )
        return Access(context, scope, None, "")

    @app.get("/health/ready")
    async def ready():
        current = await app.state.executor.runner.describe()
        if current["environment_digest"] != app.state.executor.environment_digest:
            return JSONResponse({"code": "environment_changed"}, status_code=503)
        async with app.state.broker.capabilities.pool.connection() as conn:
            await conn.execute("SELECT 1")
        return {
            "status": "ready",
            "build_id": app.state.broker.documents.store.build_id,
            "environment_digest": current["environment_digest"],
            "read_limits": {
                k: getattr(app.state.broker.limits, k)
                for k in ("max_sections_per_read", "max_tokens_per_section", "max_tokens_per_read")
            },
        }

    @app.post("/data")
    async def data(body: DataRequest):
        return await app.state.broker.call(
            body.token, body.operation, body.arguments, request_id=body.request_id
        )

    @app.post("/python")
    async def python(body: PythonRequest, request: Request):
        if body.environment_digest != app.state.executor.environment_digest:
            raise AccountingError("Runner environment does not match the caller pin")
        assigned = await access(body.lease, "exploration")

        async def execute():
            with bind(assigned.context):
                return await app.state.executor.execute(
                    assigned.context,
                    body.code,
                    body.purpose,
                    body.input_refs,
                    request_id=body.request_id,
                    analysis_provenance=body.analysis_provenance,
                )

        work = asyncio.create_task(execute())
        try:
            while not work.done():
                await asyncio.wait({work}, timeout=0.25)
                if await request.is_disconnected():
                    raise asyncio.CancelledError()
            return await work
        finally:
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
            await assigned.context.resources.drain_attempt(assigned.context.lease.attempt_id)

    @app.post("/artifact")
    async def artifact(body: ArtifactRequest):
        assigned = await access(body.lease)
        row = await app.state.broker.records.get(assigned, body.ref, kinds=["artifact"])
        return await asyncio.to_thread(app.state.broker.artifacts.load, row)

    @app.post("/retain")
    async def retain(body: RetainRequest):
        await app.state.broker.artifacts.retain(await access(body.lease), body.refs)
        return {"retained": True}

    @app.post("/maintenance")
    async def maintenance():
        await app.state.broker.artifacts.prune()
        await app.state.executor.prune()
        return {"complete": True}

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_broker_app(), host="0.0.0.0", port=8002, log_config=None)
