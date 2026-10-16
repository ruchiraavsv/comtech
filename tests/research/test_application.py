"""R6: real HTTP API/broker, PostgreSQL and restricted runner; synthetic providers."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pydantic import SecretStr

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import Limits
from comtech.db import database
from comtech.research.access import Capabilities
from comtech.research.accounting import CURRENT, Resources
from comtech.research.broker import Broker
from comtech.research.operations import Maintenance
from comtech.research.python_execution import PythonExecutor
from comtech.research.runner_client import RunnerClient
from comtech.research.service import create_broker_app
from comtech.research.transport import PrivateClient, lease_json
from comtech.retrieval.embedding import QueryEmbedding
from comtech.retrieval.search import HybridSearch
from tests.agents.helpers import FakeModel, FakeTools
from tests.retrieval.test_sources import BUILD, make_release
from tests.test_integration import collect, http_server, server
from tests.test_integration import settings as settings

from .test_agent import Script, draft
from .test_runner import ready

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_RUNNER_TESTS") != "1", reason="Requires isolated runner"),
]
SECRET = "synthetic-private-service-token-32-characters"


class Model(Script):
    def __init__(self, mode, counter):
        self.mode, self.ordinary = mode, FakeModel()
        self.entered = asyncio.Event()
        super().__init__(self.response, counter)

    async def generate(self, role, payload, schema, maximum):
        if self.mode == "ordinary":
            return await self.ordinary.generate(role, payload, schema, maximum)
        return await super().generate(role, payload, schema, maximum)

    def response(self, role, payload):
        mode = self.mode
        if role == "supervisor":
            if not payload["task_results"]:
                return {
                    "decision": {
                        "action": "delegate",
                        "resolved_request": "Synthetic inquiry",
                        "calls": [
                            {
                                "specialist": "research",
                                "task": {
                                    "task_id": "r1",
                                    "objective": "Establish selected facts",
                                    "analysis_mode": "semantic"
                                    if mode in ("partial", "recursive")
                                    else "deterministic"
                                    if mode == "cancel"
                                    else mode,
                                    "expected_output": "Supported finding",
                                },
                            }
                        ],
                    }
                }
            result = payload["task_results"]["r1"]["result"]
            claims = [
                {
                    "claim_id": c["claim_id"],
                    "statement": c["statement"],
                    "support": c["support"],
                    "evidence_ids": [e["evidence_id"] for e in c["evidence"]],
                    "source_task_ids": ["r1"],
                    "computation_ref": c.get("computation_ref"),
                    "premise_claim_ids": c.get("premise_claim_ids", []),
                    "derivation": c.get("derivation"),
                }
                for c in result["claims"]
            ]
            return {
                "decision": {
                    "action": "submit",
                    "answer": {
                        "resolved_request": "Synthetic inquiry",
                        "claims": claims,
                        "unresolved": result["unresolved"],
                        "limitations": [],
                        "source_conflicts": [],
                        "clarification": None,
                    },
                }
            }
        if role == "review":
            return {
                "status": "approved",
                "issues": [],
                "required_changes": [],
                "followup_tasks": [],
            }
        if role == "final":
            claims = payload["answer_package"]["claims"]
            return {
                "paragraphs": [
                    {"text": c["statement"], "claim_ids": [c["claim_id"]]} for c in claims
                ]
            }
        if role == "research_finalize":
            if mode in ("semantic", "partial", "recursive"):
                return draft(payload, inherited=bool(payload["child_claims"]))
            return {
                "status": "answered",
                "claims": [
                    {
                        "claim_id": "computed",
                        "statement": "The selected observations have a positive character count.",
                        "support": "derived",
                        "evidence": [],
                        "computation_ref": next(
                            k for k in payload["artifacts"] if k.startswith("ART-")
                        ),
                        "derivation": "Sum character lengths of the selected spans only.",
                    }
                ],
                "unresolved": [],
            }
        assert role == "research"
        if mode == "partial" and payload["failures"]:
            return {"decision": {"action": "finalize"}}
        if payload["child_claims"] or any(k.startswith("ART-") for k in payload["artifacts"]):
            return {"decision": {"action": "finalize"}}
        if mode == "recursive" and payload["task"]["depth"] == 0:
            return {
                "decision": {
                    "action": "delegate",
                    "children": [
                        {
                            "description": "Inspect Alpha ordering",
                            "expected_output": "Supported ordering",
                            "analysis_mode": "semantic",
                            "narrowed_scope": payload["task"]["narrowed_scope"],
                            "input_refs": [],
                            "partition": "alpha",
                            "gap": "Ordering",
                            "reason": "Independent section inspection",
                            "expected_information_gain": "Ordering",
                        }
                    ],
                }
            }
        if not payload["evidence"]:
            return {
                "decision": {
                    "action": "knowledge_search",
                    "arguments": {"query": "commit", "service_ids": ["svc-0"]},
                }
            }
        if mode in ("semantic", "partial", "recursive"):
            return {"decision": {"action": "finalize"}}
        code = """
import numpy as np
read = data.read_document_sections('DOC-0', 'commit')
length = int(np.sum([len(o['content']) for o in read['observations']]))
artifact = data.write_artifact({'length':length}, 'json',
    [o['observation_id'] for o in read['observations']],
    method='Sum selected span lengths', units='characters',
    assumptions=['Selected spans only; not the corpus'])
result = {'artifact_ref':artifact['artifact_ref'], 'length':length}
"""
        if mode == "cancel":
            code = "while True:\n    pass"
        return {
            "decision": {
                "action": "execute_python",
                "code": code,
                "purpose": "Count selected text",
                "input_refs": list(payload["evidence"]),
            }
        }


@asynccontextmanager
async def configured(settings, monkeypatch, tmp_path, mode):
    store = make_release(tmp_path / "sources", ["Alpha: commit before dispatch.\n---\nMore alpha."])
    settings.agent_mode, settings.background_enabled, settings.research_enabled = (
        "enterprise",
        True,
        True,
    )
    settings.research_service_token = SecretStr(SECRET)
    settings.agent_build_id, settings.ingestion_artifact_root = BUILD, tmp_path / "sources"
    resources, counter = Resources(), TokenCounter()
    model = Model(mode, counter)
    calls, embeddings = [], []
    endpoint = {}

    class Embeddings:
        async def create(self, **kw):
            embeddings.append(kw)
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
                usage=SimpleNamespace(total_tokens=5),
            )

    provider = SimpleNamespace(embeddings=Embeddings())
    fixed = QueryEmbedding(provider, counter, model=store.manifest["config"]["model"], dimensions=3)

    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"matches": [{"_id": "DOC-0:v1:s0:p1"}]})

    async def embed(query):
        client = PrivateClient(endpoint["api"], SECRET)
        try:
            return (
                await client.call(
                    "/internal/research/embed", {"lease": lease_json(CURRENT.get()), "query": query}
                )
            )["vector"]
        finally:
            await client.close()

    async with database(settings.require_database()) as pool:
        search = HybridSearch(
            store,
            SimpleNamespace(pinecone_api_key=SecretStr("synthetic")),
            None,
            counter,
            httpx.AsyncClient(transport=httpx.MockTransport(handle)),
            embed_query=embed,
        )
        broker = Broker(
            Capabilities(pool, resources), store, search, counter, Limits(), tmp_path / "artifacts"
        )
        runner = RunnerClient(os.environ["RESEARCH_RUNNER_SOCKET"])
        info = await ready(runner)
        executor = PythonExecutor(broker, runner, info["environment_digest"])
        app = create_broker_app(settings, broker=broker, executor=executor)
        # Keep the actual application runtime, service client, graph and scheduler wiring.
        model.client = provider

        async def close():
            pass

        model.close = close
        monkeypatch.setattr("comtech.agents.runtime.StructuredModel", lambda *a: model)
        monkeypatch.setattr("comtech.agents.runtime.SourceStore", lambda *a: store)
        monkeypatch.setattr(
            "comtech.agents.runtime.HybridSearch",
            lambda *a: SimpleNamespace(embed_query=fixed, close=close),
        )
        monkeypatch.setattr(
            "comtech.agents.runtime.NorthstarClient", lambda *a: SimpleNamespace(discover=close)
        )
        monkeypatch.setattr("comtech.agents.runtime.KnowledgeTools", lambda *a: FakeTools())
        try:
            async with http_server(app) as private:
                settings.research_broker_url = str(private.base_url)
                yield SimpleNamespace(
                    pool=pool,
                    broker=broker,
                    app=app,
                    model=model,
                    endpoint=endpoint,
                    private=private,
                    embeddings=embeddings,
                    calls=calls,
                )
        finally:
            await resources.drain()
            await search.close()


@pytest.mark.parametrize("mode", ["ordinary", "semantic", "deterministic", "mixed"])
async def test_four_routes_and_replay(settings, monkeypatch, tmp_path, mode):
    async with configured(settings, monkeypatch, tmp_path, mode) as b:
        async with server(settings) as client:
            b.endpoint["api"] = str(client.base_url)
            assert (await client.get("/health/ready")).json()["research_enabled"]
            body = {
                "thread_id": str(uuid4()),
                "message": "Synthetic bounded inquiry",
                "execution_mode": "background",
                "idempotency_key": uuid4().hex,
            }
            submissions = await asyncio.gather(
                *(client.post("/api/runs", json=body) for _ in range(3))
            )
            assert {r.status_code for r in submissions} == {202}
            run = submissions[0].json()
            assert len({r.json()["run_id"] for r in submissions}) == 1
            _, events = await collect(client, "GET", run["events_url"])
            state = (await client.get(f"/api/runs/{run['run_id']}")).json()
            assert state["status"] == "completed", (state, events)
            result = (await client.get(run["result_url"])).json()
            assert result["review_status"] == "approved" and "[1]" in result["answer"]
            answers = [e for _, e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
            assert len(answers) == 1
            assert "import numpy" not in json.dumps(events)
            _, replay = await collect(
                client, "GET", run["events_url"], headers={"Last-Event-ID": events[0][0]}
            )
            assert replay == events[1:]
            if mode != "ordinary":
                assert b.embeddings and state["progress"]["selected_coverage"]
                assert result["research"]["selected_refs"]
                assert state["progress"]["usage"]["embedding_requests"]["used"] == 1
                assert state["progress"]["usage"]["python_executions"]["used"] == (
                    mode != "semantic"
                )
            before = len(b.model.calls)
        async with server(settings) as client:
            b.endpoint["api"] = str(client.base_url)
            assert (await client.get(run["result_url"])).json() == result
            assert len(b.model.calls) == before


async def test_private_auth_readiness_and_expired_result(settings, monkeypatch, tmp_path):
    async with configured(settings, monkeypatch, tmp_path, "semantic") as b:
        assert (await b.private.get("/health/ready")).status_code == 401
        assert (
            await b.private.post(
                "/data", content=b"x" * 140000, headers={"Authorization": "Bearer " + SECRET}
            )
        ).status_code == 413
        async with server(settings) as client:
            b.endpoint["api"] = str(client.base_url)
            assert (await client.post("/internal/research/embed", json={})).status_code in (
                401,
                422,
            )
            run = (
                await client.post(
                    "/api/runs",
                    json={
                        "message": "Fact",
                        "execution_mode": "background",
                        "idempotency_key": uuid4().hex,
                    },
                )
            ).json()
            await collect(client, "GET", run["events_url"])
            path = f"/api/runs/{run['run_id']}"
            assert (await client.get(path)).json()["status"] == "completed"
            async with b.pool.connection() as conn:
                await conn.execute(
                    "UPDATE app_runs SET result_expires_at=clock_timestamp()-interval '1 second' "
                    "WHERE id=%s",
                    (run["run_id"],),
                )
            assert (await client.get(run["result_url"])).status_code == 410
            assert (await client.get(path + "/events")).status_code == 410
            await Maintenance(b.pool, AsyncPostgresSaver(b.pool), None, 300).prune()
            assert (await client.get(path)).json()["result_expired"]
            original = b.app.state.executor.environment_digest
            b.app.state.executor.environment_digest = "f" * 64
            assert (await client.get("/health/ready")).status_code == 503
            b.app.state.executor.environment_digest = original


@pytest.mark.parametrize("mode", ["recursive", "partial"])
async def test_recursion_and_tool_outage_partial(settings, monkeypatch, tmp_path, mode):
    async with configured(settings, monkeypatch, tmp_path, mode) as b:
        if mode == "partial":

            async def unavailable(*args, **kwargs):
                raise httpx.ConnectError("Synthetic source outage")

            b.broker.tools.search.http.post = unavailable
        async with server(settings) as client:
            b.endpoint["api"] = str(client.base_url)
            run = (
                await client.post(
                    "/api/runs",
                    json={
                        "message": "Synthetic inquiry",
                        "execution_mode": "background",
                        "idempotency_key": uuid4().hex,
                    },
                )
            ).json()
            _, events = await collect(client, "GET", run["events_url"])
            state = (await client.get(f"/api/runs/{run['run_id']}")).json()
            assert state["status"] == "completed", (state, events)
            result = (await client.get(run["result_url"])).json()
            if mode == "partial":
                assert result["answer_package"]["unresolved"]
                assert not result["answer_package"]["claims"]
            else:
                assert (
                    sum(t["count"] for t in state["progress"]["tasks"] if t["kind"] == "research")
                    == 2
                )
                assert "Alpha" in result["answer"]


async def test_cancel_stops_remote_python(settings, monkeypatch, tmp_path):
    async with configured(settings, monkeypatch, tmp_path, "cancel") as b:
        async with server(settings) as client:
            b.endpoint["api"] = str(client.base_url)
            run = (
                await client.post(
                    "/api/runs",
                    json={
                        "message": "Synthetic cancellation",
                        "execution_mode": "background",
                        "idempotency_key": uuid4().hex,
                    },
                )
            ).json()
            async with asyncio.timeout(12):
                while True:
                    async with b.pool.connection() as conn:
                        active = await (
                            await conn.execute(
                                "SELECT e.id FROM research_executions e JOIN research_objectives o "
                                "ON o.id=e.objective_id WHERE o.run_id=%s "
                                "AND e.record->>'kind'='python' AND e.state='running'",
                                (run["run_id"],),
                            )
                        ).fetchone()
                    if active:
                        break
                    await asyncio.sleep(0.05)
            path = f"/api/runs/{run['run_id']}"
            assert (await client.post(path + "/cancel")).json()["status"] == "cancelled"
            async with asyncio.timeout(5):
                while True:
                    async with b.pool.connection() as conn:
                        row = await (
                            await conn.execute(
                                "SELECT state FROM research_executions WHERE id=%s", (active["id"],)
                            )
                        ).fetchone()
                    if row["state"] != "running":
                        break
                    await asyncio.sleep(0.05)
            _, events = await collect(client, "GET", run["events_url"])
            assert not any(e["type"] == "TEXT_MESSAGE_CONTENT" for _, e in events)
            assert (await client.get(run["result_url"])).status_code == 409


async def test_research_checkpoint_recovery_before_queue_commit(settings, monkeypatch, tmp_path):
    from comtech.research.agent import ResearchAgent

    reached = asyncio.Event()
    original = ResearchAgent.__call__

    async def interrupted(agent, claim):
        outcome = await original(agent, claim)
        reached.set()
        await asyncio.Event().wait()
        return outcome

    monkeypatch.setattr(ResearchAgent, "__call__", interrupted)
    async with configured(settings, monkeypatch, tmp_path, "semantic") as b:
        async with server(settings) as client:
            b.endpoint["api"] = str(client.base_url)
            run = (
                await client.post(
                    "/api/runs",
                    json={
                        "message": "Recover committed research",
                        "execution_mode": "background",
                        "idempotency_key": uuid4().hex,
                    },
                )
            ).json()
            await asyncio.wait_for(reached.wait(), 12)
            before = len([r for r, _ in b.model.calls if r.startswith("research")])
        monkeypatch.setattr(ResearchAgent, "__call__", original)
        async with server(settings) as client:
            b.endpoint["api"] = str(client.base_url)
            _, events = await collect(client, "GET", run["events_url"])
            state = (await client.get(f"/api/runs/{run['run_id']}")).json()
            assert state["status"] == "completed", (state, events)
            assert len([r for r, _ in b.model.calls if r.startswith("research")]) == before
            assert len([e for _, e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]) == 1
            assert len(b.embeddings) == 1
