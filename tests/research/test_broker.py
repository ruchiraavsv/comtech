"""Real Postgres, synthetic published release and scripted Pinecone/embedding responses."""

import json
import os
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from psycopg.types.json import Jsonb

from comtech.agents.budget import TokenCounter, digest
from comtech.agents.contracts import Limits, ReadDocumentSectionsResult
from comtech.agents.tools import KnowledgeTools
from comtech.research.access import Capabilities
from comtech.research.broker import Broker, ResearchDocumentTools
from comtech.research.broker_contracts import DOCUMENT_FIELDS, OPERATIONS, BrokerError
from comtech.research.contracts import SourceScope
from comtech.research.control import Control
from comtech.research.delivery import Delivery
from comtech.research.ledger import RunClosed
from comtech.research.queue import TaskQueue
from comtech.retrieval.search import HybridSearch
from tests.retrieval.test_sources import BUILD, make_release

from .helpers import accounting_context

pytestmark = pytest.mark.integration


@pytest.fixture
async def bundle(research_pool, tmp_path):
    ctx, run = await accounting_context(research_pool)
    store = make_release(
        tmp_path / "sources",
        [
            "Alpha: commit before dispatch.\n---\nMore alpha.",
            "Beta: independent policy.",
            "Long material. " * 1000,
        ],
    )
    scope = SourceScope(
        scope_ref="documents",
        sources=["documents"],
        datasets={"documents": ["documents"]},
        fields={"documents": [*DOCUMENT_FIELDS, "content"]},
        capabilities=list(OPERATIONS),
        pinned_versions={"documents": BUILD},
    )
    async with research_pool.connection() as conn:
        await conn.execute(
            "UPDATE research_objectives SET scope=%s,pinned_versions=%s WHERE id=%s",
            (
                Jsonb(scope.model_dump(mode="json")),
                Jsonb(scope.pinned_versions),
                ctx.lease.objective_id,
            ),
        )
    counter, limits = TokenCounter(), Limits()
    requests, embeddings = [], []

    class Embeddings:
        async def create(self, **kw):
            embeddings.append(kw)
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
                usage=SimpleNamespace(total_tokens=5),
            )

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        ids = body["filter"]["document_id"]["$in"]
        return httpx.Response(200, json={"matches": [{"_id": key + ":v1:s0:p1"} for key in ids]})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    search = HybridSearch(
        store,
        SimpleNamespace(pinecone_api_key=SimpleNamespace(get_secret_value=lambda: "synthetic")),
        SimpleNamespace(embeddings=Embeddings()),
        counter,
        http,
    )
    caps = Capabilities(research_pool, ctx.resources)
    await caps.register_scope(ctx.lease, scope)
    token = await caps.issue(ctx.lease)
    broker = Broker(caps, store, search, counter, limits, tmp_path / "artifacts")
    yield SimpleNamespace(
        ctx=ctx,
        run=run,
        store=store,
        scope=scope,
        caps=caps,
        token=token,
        broker=broker,
        requests=requests,
        embeddings=embeddings,
    )
    await ctx.resources.drain()
    await search.close()


async def call(b, op, args=None, key=None, token=None):
    return await b.broker.call(token or b.token, op, args or {}, request_id=key or uuid4().hex)


async def test_read_limit_feedback_is_shared_by_worker_and_broker(bundle):
    b = bundle
    tools = KnowledgeTools(b.store, b.broker.tools.search, None, b.broker.counter, b.broker.limits)
    args = {"document_id": "DOC-0", "query": "commit", "max_sections": 6}
    worker = await tools.call("read_document_sections", args)
    research = await call(b, "read_document_sections", args)
    assert worker.error.code == research["value"]["error"]["code"] == "INVALID_ARGUMENT"
    assert worker.error.message == research["value"]["error"]["message"]
    assert "between 1 and 3" in worker.error.message
    assert not research["receipt_ref"]
    args["max_sections"] = 1
    corrected = await call(b, "read_document_sections", args)
    assert corrected["value"]["observations"]
    assert corrected["value"]["section_options"][0]["section_id"] == "DOC-0:v1:s1"
    b.broker.limits.max_sections_per_read = 1
    defaulted = await call(b, "read_document_sections", {"document_id": "DOC-0", "query": "alpha"})
    assert len(defaulted["value"]["observations"]) == 1


async def test_exact_document_shorthand_does_not_expand_read_scope(bundle):
    b = bundle
    result = await b.broker.tools.call(
        "read_document_sections", {"document_id": "0", "query": "commit"}, allowed_ids={"DOC-0"}
    )
    assert result.document_id == "DOC-0"
    assert all(o.source_ref.source_id == "DOC-0" for o in result.observations)
    with pytest.raises(ValueError, match="outside the assigned scope"):
        await b.broker.tools.call(
            "read_document_sections", {"document_id": "1", "query": "commit"}, allowed_ids={"DOC-0"}
        )
    with pytest.raises(ValueError, match="Unknown document selector"):
        await b.broker.tools.call(
            "read_document_sections", {"document_id": "missing", "query": "commit"}
        )


async def execution_token(b):
    execution = uuid4()
    async with b.caps.pool.connection() as conn:
        await conn.execute(
            """INSERT INTO research_executions
            (id,objective_id,task_id,attempt_id,operation_key,request_hash,state,record)
            VALUES(%s,%s,%s,%s,%s,'synthetic','running',%s)""",
            (
                execution,
                b.ctx.lease.objective_id,
                b.ctx.lease.task_id,
                b.ctx.lease.attempt_id,
                str(execution),
                Jsonb(
                    {
                        "code_hash": digest("synthetic calculation"),
                        "environment_digest": "synthetic-image",
                    }
                ),
            ),
        )
    return await b.caps.issue(b.ctx.lease, execution_id=execution)


@pytest.mark.parametrize("ceiling", [2, 3])
async def test_large_enumeration_page_reserves_at_most_pinned_population(bundle, ceiling):
    from comtech.research.ledger import BudgetExhausted

    b = bundle
    async with b.caps.pool.connection() as conn:
        await conn.execute(
            "UPDATE research_budget_counters SET ceiling=%s WHERE objective_id=%s "
            "AND metric='documents_discovered'",
            (ceiling, b.ctx.lease.objective_id),
        )
    if ceiling == 2:
        with pytest.raises(BudgetExhausted):
            await call(b, "enumerate_documents", {"limit": 1000})
    else:
        reply = await call(b, "enumerate_documents", {"limit": 1000})
        assert len(reply["value"]["items"]) == 3
        assert not reply["value"]["truncated"] and reply["receipt_ref"]
    counts = await b.ctx.ledger.counters(b.ctx.lease.objective_id)
    assert counts["documents_discovered"]["used"] == (3 if ceiling == 3 else 0)


async def test_shared_search_and_expansion_shapes_and_accounting(bundle):
    b = bundle
    direct = ResearchDocumentTools(b.broker, b.token)
    ordinary = KnowledgeTools(
        b.store, b.broker.tools.search, None, b.broker.counter, b.broker.limits
    )
    assert direct.schemas == {k: ordinary.schemas[k] for k in direct.schemas}
    found = await direct.call(
        "knowledge_search", {"query": "Alpha", "service_ids": ["svc-0"]}, request_id="search"
    )
    assert len(found.observations) == 1 and found.observations[0].source_ref.source_id == "DOC-0"
    assert len(b.requests) == 2 and len(b.embeddings) == 1
    assert all(r["filter"] == {"document_id": {"$in": ["DOC-0"]}} for r in b.requests)
    assert b.embeddings[0]["model"] == "test-embedding" and b.embeddings[0]["dimensions"] == 3
    read = await direct.call(
        "read_document_sections", {"document_id": "DOC-0", "query": "commit"}, request_id="read"
    )
    assert isinstance(read, ReadDocumentSectionsResult)
    assert "commit before dispatch" in read.observations[0].content
    assert b.broker.counter.count(read) <= 3000
    counts = await b.ctx.ledger.counters(b.ctx.lease.objective_id)
    assert counts["data_requests"]["used"] == 2
    assert counts["source_requests"]["used"] == 3
    assert counts["embedding_requests"]["used"] == 1 and counts["embedding_tokens"]["used"] == 5
    assert counts["documents_discovered"]["used"] == 1 and counts["documents_opened"]["used"] == 1
    assert counts["python_executions"]["used"] == 0


async def test_registered_expansion_counts_durable_ids_within_shared_limit(bundle, tmp_path):
    b = bundle
    store = make_release(
        tmp_path / "long-release", ["\n---\n".join(["Long material. " * 1000] * 3)]
    )
    b.broker.tools.store = store
    b.broker.documents.store = store
    direct = ResearchDocumentTools(b.broker, b.token)
    result = await direct.call(
        "read_document_sections", {"document_id": "DOC-0", "query": "material"}, request_id="long"
    )
    assert isinstance(result, ReadDocumentSectionsResult) and result.observations
    assert result.token_count == b.broker.counter.count(result) <= 3000
    assert all(o.is_partial for o in result.observations)
    for item in result.observations:
        source = item.source_ref
        assert item.content == store.sources["DOC-0"][source.char_start : source.char_end]


async def test_capability_scope_tokens_fields_and_mcp_denials(bundle):
    b = bundle
    for op in ("lookup", "query", "get_service", "grant", "execute_sql"):
        with pytest.raises(BrokerError, match="unavailable"):
            await call(b, op)
    with pytest.raises(BrokerError, match="unknown"):
        await call(b, "describe", token="forged")
    broader = b.scope.model_copy(update={"pinned_versions": {"documents": "changed"}})
    with pytest.raises(BrokerError):
        await b.caps.register_scope(b.ctx.lease, broader)
    with pytest.raises(BrokerError):
        await call(b, "knowledge_search", {"query": "Alpha", "url": "https://example.invalid"})
    page = await call(b, "enumerate_documents", {"fields": ["source_locator"]})
    assert page["value"]["error"]["code"] == "INVALID_ARGUMENT"
    await b.caps.revoke(b.token)
    with pytest.raises(BrokerError):
        await call(b, "describe")


async def test_narrow_document_scope_filters_both_search_branches(bundle):
    b = bundle
    # Provision a narrower child through the queue and trusted registration path.
    queue = TaskQueue(b.caps.pool)
    child = await queue.enqueue(b.ctx.lease, "narrow", "research", {}, {})
    claim = await queue.claim(uuid4(), ["research"])
    assert claim.lease.task_id == child["id"]
    narrow = b.scope.model_copy(update={"scope_ref": "narrow", "document_ids": ["DOC-1"]})
    await b.caps.register_scope(claim.lease, narrow)
    token = await b.caps.issue(claim.lease)
    found = await call(b, "knowledge_search", {"query": "policy"}, token=token)
    assert [o["source_ref"]["source_id"] for o in found["value"]["observations"]] == ["DOC-1"]
    assert all(r["filter"]["document_id"]["$in"] == ["DOC-1"] for r in b.requests)
    denied = await call(
        b, "read_document_sections", {"document_id": "DOC-0", "query": "Alpha"}, token=token
    )
    assert denied["value"]["error"]
    with pytest.raises(BrokerError, match="immutable"):
        await b.caps.register_scope(claim.lease, b.scope)


async def test_observation_metadata_must_also_be_in_field_scope(bundle):
    b = bundle
    queue = TaskQueue(b.caps.pool)
    await queue.enqueue(b.ctx.lease, "restricted-fields", "research", {}, {})
    claim = await queue.claim(uuid4(), ["research"])
    await b.caps.register_scope(
        claim.lease, b.scope.model_copy(update={"fields": {"documents": ["content"]}})
    )
    token = await b.caps.issue(claim.lease)
    result = await call(b, "knowledge_search", {"query": "policy"}, token=token)
    assert result["value"]["error"]["code"] == "SCOPE_DENIED"
    assert not b.requests and not b.embeddings


async def test_enumeration_coverage_cursors_exact_spans_and_unknown_metadata(bundle):
    b = bundle
    description = await call(b, "describe")
    assert description["value"]["total_count"] == 3
    first = await call(b, "enumerate_documents", {"limit": 1})
    page = first["value"]
    assert page["coverage"]["total_count"] == 3 and not page["coverage"]["semantic_inspection"]
    assert page["items"][0]["classification"] is None
    assert "source_locator" not in page["items"][0]
    assert page["truncated"] and page["next_cursor"]
    invalid = await call(b, "enumerate_documents", {"limit": 2, "cursor": page["next_cursor"]})
    assert invalid["value"]["error"]["code"] == "INVALID_CURSOR"
    second = await call(b, "enumerate_documents", {"limit": 1, "cursor": page["next_cursor"]})
    assert second["value"]["items"][0]["document_id"] == "DOC-1"
    third = await call(
        b, "enumerate_documents", {"limit": 1, "cursor": second["value"]["next_cursor"]}
    )
    assert third["value"]["next_cursor"] is None
    docref = third["value"]["items"][0]["document_ref"]
    args = {"document_ref": docref, "max_chars": 4000}
    contents = []
    while True:
        result = (await call(b, "read_spans", args))["value"]
        assert "error" not in result
        item = result["observations"][0]
        a, z = item["source_ref"]["char_start"], item["source_ref"]["char_end"]
        assert b.store.sources["DOC-2"][a:z] == item["content"]
        contents.append(item["content"])
        if not result["next_cursor"]:
            break
        args["cursor"] = result["next_cursor"]
    assert "".join(contents) == b.store.sources["DOC-2"]
    assert (await b.ctx.ledger.counters(b.ctx.lease.objective_id))["documents_opened"]["used"] == 1


async def test_replay_identity_and_restart_keep_receipts_and_usage(bundle):
    b = bundle
    first = await call(b, "knowledge_search", {"query": "Alpha"}, key="stable")
    counts = await b.ctx.ledger.counters(b.ctx.lease.objective_id)
    assert await call(b, "knowledge_search", {"query": "Alpha"}, key="stable") == first
    assert await b.ctx.ledger.counters(b.ctx.lease.objective_id) == counts
    with pytest.raises(BrokerError, match="immutable"):
        await call(b, "knowledge_search", {"query": "different"}, key="stable")
    await Control(b.caps.pool, Delivery(b.caps.pool)).recover({"documents": BUILD})
    claim = await TaskQueue(b.caps.pool).claim(uuid4(), ["supervisor"])
    token = await b.caps.issue(claim.lease)
    assert await call(b, "knowledge_search", {"query": "Alpha"}, key="stable", token=token) == first
    assert len(b.embeddings) == 1
    assert await b.ctx.ledger.counters(b.ctx.lease.objective_id) == counts
    with pytest.raises(RunClosed):
        await call(b, "describe")


@pytest.mark.parametrize("format", ["json", "parquet"])
async def test_artifact_roundtrip_provenance_hashes_and_expiry(bundle, format):
    b = bundle
    read = await call(b, "read_document_sections", {"document_id": "DOC-0", "query": "Alpha"})
    ref = read["value"]["observations"][0]["observation_id"]
    token = await execution_token(b)
    rows = [{"category": "observed", "count": 1}, {"category": "unknown", "count": None}]
    saved = await call(
        b,
        "write_artifact",
        {"value": rows, "format": format, "input_refs": [ref], "method": "synthetic extraction"},
        token=token,
    )
    assert "error" not in saved["value"]
    artifact = saved["value"]["artifact_ref"]
    result = await call(b, "read_artifact", {"artifact_ref": artifact, "limit": 1})
    assert result["value"]["items"] == rows[:1] and result["value"]["truncated"]
    more = await call(
        b,
        "read_artifact",
        {"artifact_ref": artifact, "limit": 1, "cursor": result["value"]["next_cursor"]},
    )
    assert more["value"]["items"] == rows[1:]
    access = await b.caps.resolve(b.token, "read_artifact")
    entry = await b.broker.records.get(access, artifact)
    assert entry["payload"]["code_hash"] == digest("synthetic calculation")
    assert entry["input_refs"] == [ref]
    await b.broker.artifacts.retain(access, [artifact])
    async with b.caps.pool.connection() as conn:
        retained = await (
            await conn.execute("SELECT retained FROM research_data_records WHERE ref=%s", (ref,))
        ).fetchone()
        assert retained["retained"]
        await conn.execute(
            "UPDATE research_data_records SET expires_at=now()-interval '1 day' WHERE ref=%s",
            (artifact,),
        )
    assert await b.broker.artifacts.prune() == 0  # Active evidence cannot be purged.
    path = b.broker.artifacts.path(entry["objective_id"], entry["payload"]["key"])
    orphan = path.parent / uuid4().hex
    orphan.write_bytes(b"unfinished synthetic write")
    old = time.time() - 8 * 86400
    os.utime(orphan, (old, old))
    unmanaged = path.parent / "keep.txt"
    unmanaged.write_text("unmanaged", encoding="utf-8")
    os.utime(unmanaged, (old, old))
    await b.broker.artifacts.prune_orphans()
    assert orphan.exists()  # Active objectives pin unfinished writes too.
    async with b.caps.pool.connection() as conn:
        await conn.execute(
            "UPDATE research_data_records SET expired=true WHERE ref=%s", (artifact,)
        )
    expired_read = await call(b, "read_artifact", {"artifact_ref": artifact})
    assert expired_read["value"]["error"]["code"] == "ARTIFACT_EXPIRED"
    async with b.caps.pool.connection() as conn:
        await conn.execute(
            "UPDATE research_data_records SET expired=false WHERE ref=%s", (artifact,)
        )
    path.write_bytes(b"corrupt")
    broken = await call(b, "read_artifact", {"artifact_ref": artifact})
    assert broken["value"]["error"]["code"] == "HASH_MISMATCH"
    await Control(b.caps.pool, Delivery(b.caps.pool)).cancel(b.run["id"])
    assert await b.broker.artifacts.prune() == 1 and not path.exists()
    assert not orphan.exists() and unmanaged.exists()
    async with b.caps.pool.connection() as conn:
        expired = await (
            await conn.execute(
                "SELECT expired FROM research_data_records WHERE ref=%s", (artifact,)
            )
        ).fetchone()
        assert expired["expired"]


async def test_cancel_and_expired_capability_stop_new_calls(bundle):
    b = bundle
    async with b.caps.pool.connection() as conn:
        await conn.execute(
            "UPDATE research_data_capabilities SET expires_at=now()-interval '1 second'"
        )
    with pytest.raises(BrokerError):
        await call(b, "describe")
    token = await b.caps.issue(b.ctx.lease)
    await Control(b.caps.pool, Delivery(b.caps.pool)).cancel(b.run["id"])
    with pytest.raises(RunClosed):
        await call(b, "knowledge_search", {"query": "Alpha"}, token=token)
    assert not b.requests and not b.embeddings


async def test_artifact_inheritance_requires_grant_and_complete_input_scope(bundle):
    b = bundle
    read = await call(b, "read_document_sections", {"document_id": "DOC-0", "query": "Alpha"})
    ref = read["value"]["observations"][0]["observation_id"]
    token = await execution_token(b)
    artifact = (
        await call(
            b,
            "write_artifact",
            {"value": {"count": 1}, "input_refs": [ref], "method": "selected input count"},
            token=token,
        )
    )["value"]["artifact_ref"]
    queue = TaskQueue(b.caps.pool)
    for allowed in ("DOC-0", "DOC-1"):
        await queue.enqueue(b.ctx.lease, allowed, "research", {}, {})
        child = await queue.claim(uuid4(), ["research"])
        await b.caps.register_scope(
            child.lease,
            b.scope.model_copy(
                update={
                    "scope_ref": allowed,
                    "document_ids": [allowed],
                }
            ),
        )
        child_token = await b.caps.issue(child.lease)
        denied = await call(b, "read_artifact", {"artifact_ref": artifact}, token=child_token)
        assert denied["value"]["error"]["code"] == "INVALID_REFERENCE"
        if allowed == "DOC-0":
            await b.broker.records.grant(b.ctx.lease, artifact, child.lease.task_id)
            inherited = await call(
                b, "read_artifact", {"artifact_ref": artifact}, token=child_token
            )
            assert inherited["value"]["items"] == [{"count": 1}]
            access = await b.caps.resolve(child_token, "read_artifact")
            original = await b.broker.records.get(access, ref)
            assert original["task_id"] == b.ctx.lease.task_id
        else:
            with pytest.raises(BrokerError, match="Expanded document_ids"):
                await b.broker.records.grant(b.ctx.lease, artifact, child.lease.task_id)
        await queue.transition(child.lease, state="completed", result={"synthetic": True})


async def test_admitted_artifact_grant_is_honored_by_result_export(bundle):
    from comtech.research.actions import ChildProposal, ResearchDraft
    from comtech.research.admission import Admission
    from comtech.research.result_registry import ResultRegistry

    b = bundle
    read = await call(b, "read_document_sections", {"document_id": "DOC-0", "query": "Alpha"})
    ref = read["value"]["observations"][0]["observation_id"]
    token = await execution_token(b)
    artifact = (
        await call(
            b,
            "write_artifact",
            {
                "value": {"count": 1},
                "input_refs": [ref],
                "method": "Count selected observations",
            },
            token=token,
        )
    )["value"]["artifact_ref"]
    async with b.caps.pool.connection() as conn:
        await conn.execute(
            "UPDATE research_executions SET state='success',record=record || %s "
            "WHERE id=(SELECT execution_id FROM research_data_records WHERE ref=%s)",
            (
                Jsonb(
                    {
                        "started_at": "2026-10-04T00:00:00Z",
                        "finished_at": "2026-10-04T00:00:01Z",
                        "limits": {"seconds": 1},
                    }
                ),
                artifact,
            ),
        )
    queue = TaskQueue(b.caps.pool)
    (child_id,) = await Admission(queue).propose(
        b.ctx.lease,
        [
            ChildProposal(
                description="Verify the existing count",
                expected_output="Supported count",
                analysis_mode="mixed",
                narrowed_scope=b.scope,
                input_refs=[artifact],
                partition="followup",
                gap="Verify count",
                reason="Review request",
                expected_information_gain="Verify count without rerunning supported work",
            )
        ],
    )
    child = await queue.claim(uuid4(), ["research"])
    assert child.task["id"] == child_id
    child_token = await b.caps.issue(child.lease)
    access = await b.caps.resolve(child_token, "read_artifact")
    result_registry = ResultRegistry(b.broker)
    registry = await result_registry.load(access, [artifact])
    assert registry.grants[str(child_id)] >= {artifact, ref}
    draft = ResearchDraft.model_validate(
        {
            "status": "answered",
            "claims": [
                {
                    "claim_id": "count",
                    "statement": "Count is 1.",
                    "support": "derived",
                    "evidence": [],
                    "derivation": "Count the registered input.",
                    "computation_ref": artifact,
                }
            ],
            "unresolved": [],
        }
    )
    envelope = result_registry.finalize(registry, str(child_id), draft, "completed", [])
    assert envelope.artifact_refs == [artifact]
    assert envelope.evidence[ref].task_id == str(b.ctx.lease.task_id)
    assert registry.artifacts[artifact].task_id == str(b.ctx.lease.task_id)
    registry.grants[str(child_id)].remove(ref)
    with pytest.raises(ValueError, match="inheritance"):
        registry.validate_export(envelope)


async def test_changed_release_failure_missing_inputs_and_budget_admission(bundle):
    b = bundle
    token = await execution_token(b)
    invalid = await call(
        b,
        "write_artifact",
        {"value": [], "input_refs": ["invented"], "method": "count"},
        token=token,
    )
    assert invalid["value"]["error"]["code"] == "INVALID_REFERENCE"
    with pytest.raises(BrokerError):
        await call(
            b,
            "write_artifact",
            {"value": [], "format": "pickle", "input_refs": ["invented"], "method": "count"},
            token=token,
        )
    with pytest.raises(BrokerError):
        await call(
            b,
            "write_artifact",
            {"value": {"x": float("nan")}, "input_refs": ["invented"], "method": "count"},
            token=token,
        )
    b.store.build_id = "changed"
    with pytest.raises(BrokerError, match="release"):
        await call(b, "knowledge_search", {"query": "Alpha"})
    b.store.build_id = BUILD
    async with b.caps.pool.connection() as conn:
        await conn.execute(
            "UPDATE research_budget_counters SET ceiling=0 WHERE objective_id=%s "
            "AND metric='embedding_requests'",
            (b.ctx.lease.objective_id,),
        )
    from comtech.research.ledger import BudgetExhausted

    with pytest.raises(BudgetExhausted):
        await call(b, "knowledge_search", {"query": "Alpha"})
    assert not b.embeddings


async def test_source_outage_is_not_a_negative_business_fact(bundle, monkeypatch):
    b = bundle

    async def fail(*args, **kwargs):
        raise RuntimeError("synthetic outage")

    monkeypatch.setattr(b.broker.tools.search, "search", fail)
    result = await call(b, "knowledge_search", {"query": "Alpha"})
    assert result["value"]["error"]["code"] == "UNAVAILABLE"
    assert result["receipt_ref"] is None and not result["documents"]
