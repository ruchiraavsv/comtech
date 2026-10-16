import json
import ssl
from types import SimpleNamespace

import httpx
import pytest

from comtech.agents.budget import TokenCounter, digest
from comtech.agents.contracts import Limits
from comtech.retrieval.search import HybridSearch
from comtech.retrieval.store import ReadArgs, SearchArgs, SourceStore
from comtech.settings import Settings

BUILD = "1234567890abcdef"


def make_release(root, contents):
    release = root / "releases" / BUILD
    release.mkdir(parents=True)
    documents, sections, passages, summaries = [], [], [], []
    for i, text in enumerate(contents):
        doc_id = f"DOC-{i}"
        source_dir = root / "source-store"
        source_dir.mkdir(exist_ok=True)
        path = source_dir / f"{i}.md"
        path.write_bytes(text.encode())
        base = {
            "document_id": doc_id,
            "version": 1,
            "title": doc_id,
            "document_type": "policy",
            "department": "Operations",
            "service_ids": [f"svc-{i}"],
            "created_at": "2026-01-01",
            "source_locator": f"source-store/{i}.md",
            "source_sha256": digest(text),
            "namespace": "test",
            "effective_from": "2026-01-01",
            "effective_to": None,
        }
        a, ids = 0, []
        for n, part in enumerate(text.split("\n---\n")):
            sid = f"{doc_id}:v1:s{n}"
            section = {
                **base,
                "section_id": sid,
                "section_heading": f"Section {n}",
                "section_ordinal": n,
                "char_start": a,
                "char_end": a + len(part),
            }
            sections.append(section)
            passages.append({**section, "record_id": sid + ":p1", "source_text": part})
            ids.append(sid)
            a += len(part) + 5
        documents.append({**base, "section_ids": ids})
        summaries.append(
            {
                **base,
                "record_id": doc_id + ":summary",
                "summary_spans": [{"char_start": 0, "char_end": min(40, len(text))}],
            }
        )
    hashes = {}
    for name, rows in [
        ("documents", documents),
        ("sections", sections),
        ("passages", passages),
        ("summaries", summaries),
    ]:
        path = release / (name + ".jsonl")
        data = "\n".join(json.dumps(row) for row in rows) + "\n"
        path.write_bytes(data.encode())
        hashes[path.name] = digest(data)
    verification = '{"status":"passed"}'
    (release / "verification.json").write_text(verification, encoding="utf-8")
    (release / "published.json").write_text(
        json.dumps(
            {
                "build_id": BUILD,
                "status": "verified",
                "source_store_required": True,
                "verification_sha256": digest(verification),
                "artifact_sha256": hashes,
                "target": {"host": "https://test.svc.pinecone.io"},
                "config": {"model": "test-embedding", "dimensions": 3},
                "namespaces": {"test": 1},
            }
        ),
        encoding="utf-8",
    )
    return SourceStore(root, BUILD)


def test_large_document_navigates_narrower_queries_with_exact_spans(tmp_path):
    # More than 95k tokens; one oversized section includes two distant topics.
    text = (
        "ordinary background " * 26000
        + "\n\nRetry persistence: commit before dispatch.\n\n"
        + "ordinary background " * 26000
        + "\n\nReplication: asynchronous follower.\n\n"
        + "ordinary background " * 1000
    )
    store = make_release(tmp_path, [text])
    counter, limits = TokenCounter(), Limits()
    assert counter.text(text) > 95000
    first = store.read(ReadArgs(document_id="DOC-0", query="retry persistence"), counter, limits)
    second = store.read(
        ReadArgs(document_id="DOC-0", query="asynchronous follower"), counter, limits
    )
    assert "commit before dispatch" in first.observations[0].content
    assert "asynchronous follower" in second.observations[0].content
    assert first.observations[0].observation_id != second.observations[0].observation_id
    for result in (first, second):
        assert counter.count(result) <= 3000
        for item in result.observations:
            assert item.is_partial and counter.text(item.content) <= 1000
            ref = item.source_ref
            assert text[ref.char_start : ref.char_end] == item.content


def test_multiple_sections_count_serialization_and_unicode(tmp_path):
    text = "\n---\n".join(('Unicode 👋 café 日本語 and escaped "quotes". ' * 800) for _ in range(5))
    store = make_release(tmp_path, [text])
    counter = TokenCounter()
    result = store.read(ReadArgs(document_id="DOC-0", query="Unicode"), counter, Limits())
    assert 1 <= len(result.observations) <= 3
    assert counter.count(result) <= 3000
    for item in result.observations:
        assert "�" not in item.content
        assert text[item.source_ref.char_start : item.source_ref.char_end] == item.content


@pytest.mark.parametrize(
    "extra",
    [
        {"section_ids": []},
        {"section_ids": ["DOC-1:v1:s0"]},
        {"section_ids": ["DOC-0:v1:s0"] * 2},
        {"max_sections": 4},
        {"query": "   "},
    ],
)
def test_read_rejects_invalid_expansion_arguments(tmp_path, extra):
    store = make_release(tmp_path, ["first document", "second document"])
    args = ReadArgs.model_validate({"document_id": "DOC-0", "query": "first", **extra})
    with pytest.raises(ValueError):
        store.read(args, TokenCounter(), Limits())


def test_corrupt_source_and_release_rejected(tmp_path):
    make_release(tmp_path, ["source text"])
    (tmp_path / "source-store/0.md").write_text("different", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        SourceStore(tmp_path, BUILD)
    (tmp_path / "releases" / BUILD / "sections.jsonl").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        SourceStore(tmp_path, BUILD)


@pytest.mark.parametrize("read_cap", [512, 3000])
def test_omitted_sections_have_bounded_exact_navigation_without_becoming_evidence(
    tmp_path, read_cap
):
    text = "\n---\n".join(f"Requirement {i}: approved transition condition." for i in range(40))
    store = make_release(tmp_path, [text])
    counter = TokenCounter()
    limits = Limits(max_tokens_per_read=read_cap, max_tokens_per_section=min(100, read_cap))
    first = store.read(
        ReadArgs(document_id="DOC-0", query="transition", max_sections=1), counter, limits
    )
    assert first.omitted_sections and first.section_options_truncated
    assert 0 < len(first.section_options) <= 8
    assert counter.count(first) <= read_cap
    selected = first.section_options[0]["section_id"]
    assert selected not in {o.source_ref.section_id for o in first.observations}
    second = store.read(
        ReadArgs(document_id="DOC-0", query="transition", section_ids=[selected]), counter, limits
    )
    assert second.observations[0].source_ref.section_id == selected
    assert second.observations[0].content in text


async def test_hybrid_branches_share_filters_and_deduplicate_documents(tmp_path):
    store = make_release(
        tmp_path, ["Policy primary.\n---\nPolicy details.", "Other service policy."]
    )
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["filter"] == {"document_id": {"$in": ["DOC-0"]}}
        return httpx.Response(
            200, json={"matches": [{"_id": "DOC-0:v1:s0:p1"}, {"_id": "DOC-0:v1:s1:p1"}]}
        )

    class Embeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    search = HybridSearch(
        store,
        Settings(_env_file=None, pinecone_api_key="test"),
        SimpleNamespace(embeddings=Embeddings()),
        TokenCounter(),
        http,
    )
    try:
        result = await search.search(SearchArgs(query="Policy", service_ids=["svc-0"]))
    finally:
        await search.close()
    assert len(requests) == 2 and len(result.observations) == 1
    assert {r["score_by"][0]["type"] for r in requests} == {"text", "dense_vector"}
    assert result.observations[0].source_ref.source_id == "DOC-0"
    assert result.observations[0].is_partial


@pytest.mark.hosted
async def test_published_hosted_discovery_smoke():
    import os

    if os.getenv("RUN_AGENT_HOSTED_TESTS") != "1":
        pytest.skip("Opt in with RUN_AGENT_HOSTED_TESTS=1; makes paid embedding calls")
    from openai import AsyncOpenAI

    settings = Settings()
    store = SourceStore(settings.ingestion_artifact_root, settings.agent_build_id)
    async with AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        http_client=httpx.AsyncClient(verify=ssl.create_default_context()),
    ) as client:
        search = HybridSearch(store, settings, client, TokenCounter())
        try:
            result = await search.search(SearchArgs(query="service ownership", top_k=3))
        finally:
            await search.close()
    assert result.observations and all(
        o.source_ref.source_type == "document" for o in result.observations
    )
