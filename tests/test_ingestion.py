import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from comtech.ingestion.hosted import (
    Build,
    PineconeDocuments,
    ProviderError,
    schema,
    validate_schema,
)
from comtech.ingestion.prepare import chunk_spans, prepare, read_jsonl, tokens
from comtech.settings import Settings


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    settings = Settings(
        _env_file=None,
        ingestion_artifact_root=tmp_path_factory.mktemp("ingestion"),
        openai_api_key="test",
        pinecone_api_key="test",
        pinecone_index_name="test-ingestion",
    )
    result = prepare(settings)
    return settings, result


def test_corpus_integrity_and_metadata(prepared):
    settings, result = prepared
    build = Build(settings, result["build_id"])
    build.verify_sources()
    assert result["counts"] == dict(
        documents=132, sections=1054, passages=1054, summaries=132, search_records=1186
    )
    manifest = {
        d["document_id"]: d for d in read_jsonl(Path("synthetic_bank/corpus/manifest.jsonl"))
    }
    for record in build.records:
        original = manifest[record["document_id"]]
        for field in (
            "classification",
            "allowed_roles",
            "entitlements",
            "scope_operator",
            "administrator_scope_bypass",
            "effective_from",
            "status",
        ):
            assert record[field] == original[field]
        assert 0 < tokens(record["search_text"]) <= 600
        assert "canonical" not in record["source_locator"]
    summaries = read_jsonl(build.path / "summaries.jsonl")
    assert all("Ignore authorization" not in s["summary_text"] for s in summaries)
    assert all("Untrusted test attachment" not in s["summary_text"] for s in summaries)
    for s in summaries:
        assert tokens(s["summary_text"]) <= 350
    sections = read_jsonl(build.path / "sections.jsonl")
    passages = {p["record_id"]: p for p in read_jsonl(build.path / "passages.jsonl")}
    for s in sections:
        children = [passages[i] for i in s["passage_ids"]]
        assert children[0]["char_start"] == s["char_start"]
        assert children[-1]["char_end"] == s["char_end"]


@pytest.mark.parametrize(
    "text",
    [
        ("A short paragraph.\n\n" + "Large sentence café 界🙂 " * 1000),
        "\n".join(f"{i}. Keep this procedure step together." for i in range(600)),
        "| Column | Value |\n| --- | --- |\n" + "| Unicode café | 1234 |\n" * 600,
        "🙂界é" * 3000,
        "One sentence. " * 1000,
    ],
    ids=["paragraph", "list", "table", "unicode", "sentences"],
)
def test_large_sections_unicode_and_coverage(text):
    prefix = "Document: Stress fixture\nSection: Procedure\n\n"
    spans = chunk_spans(text, prefix)
    assert len(spans) > 1
    covered = 0
    previous_start = -1
    for start, end in spans:
        assert previous_start < start <= covered < end
        assert tokens(prefix + text[start:end]) <= 600
        if start < covered:
            assert tokens(text[start:covered]) <= 50
        assert "\ufffd" not in text[start:end]
        covered, previous_start = end, start
    assert covered == len(text)


def test_stable_build_and_cache_invalidation(prepared):
    settings, result = prepared
    assert prepare(settings)["build_id"] == result["build_id"]
    changed = settings.model_copy(update={"openai_embedding_dimensions": 512})
    alternate = prepare(changed)
    assert alternate["build_id"] != result["build_id"]
    one = Build(settings, result["build_id"])
    two = Build(changed, alternate["build_id"])
    assert one.records[0]["embedding_cache_key"] != two.records[0]["embedding_cache_key"]


def test_embedding_response_order_and_resume(prepared):
    settings, result = prepared
    build = Build(settings, result["build_id"])
    build.release["target"] = {"test": True}
    build.records = build.records[:70]
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("interrupted")
        rows = [
            SimpleNamespace(index=i, embedding=[float(i + 1)] * 1536)
            for i in reversed(range(len(kwargs["input"])))
        ]
        return SimpleNamespace(
            data=rows, model=kwargs["model"], usage=SimpleNamespace(total_tokens=100)
        )

    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    with pytest.raises(RuntimeError, match="interrupted"):
        build.embed(client)
    assert build.cached(build.records[0]) == [1.0] * 1536
    completed = sum(build.cached(r) is not None for r in build.records)
    assert 0 < completed < 70
    summary = build.embed(client)
    assert summary["cache_hits"] == completed
    assert summary["embedded"] == 70 - completed
    assert build.release["embedding_usage_tokens"] == 200


def test_no_publish_without_verification(prepared):
    settings, result = prepared
    build = Build(settings, result["build_id"])
    with pytest.raises(ProviderError, match="verified"):
        build.publish()
    assert not (build.path / "published.json").exists()


def test_schema_rejects_vector_only_or_wrong_dimension():
    wanted = schema(1536)
    with pytest.raises(ProviderError):
        validate_schema({}, wanted)
    with pytest.raises(ProviderError):
        validate_schema(schema(512), wanted)
    validate_schema(wanted, wanted)


def test_rest_contract_and_pagination():
    settings = Settings(_env_file=None, pinecone_api_key="test")
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        assert request.headers["X-Pinecone-Api-Version"] == "2026-07"
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={
                "documents": [{"_id": str(len(calls))}],
                "pagination": {"next": "p2"} if len(calls) == 1 else {},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pinecone = PineconeDocuments(settings, client)
    pinecone.host = "https://test.pinecone.io"
    assert pinecone.list_ids("test") == {"1", "2"}
    assert calls[1]["pagination_token"] == "p2"
    pinecone.close()


def test_interrupted_upload_is_idempotent_and_unpublished(prepared, monkeypatch):
    settings, result = prepared
    build = Build(settings, result["build_id"])
    build.records = build.records[:25]
    monkeypatch.setattr(build, "preflight", lambda _: None)
    monkeypatch.setattr(build, "cached", lambda _: [0.1] * 1536)
    saved, calls = {}, []

    def data(namespace, operation, payload):
        assert operation == "upsert"
        calls.append(payload)
        if len(calls) == 2:
            raise ProviderError("interrupted")
        saved.update({d["_id"]: d for d in payload["documents"]})
        return {"upserted_count": len(payload["documents"])}

    provider = SimpleNamespace(data=data)
    with pytest.raises(ProviderError, match="interrupted"):
        build.upload(provider)
    assert len(saved) == 20
    assert build.release["status"] == "uploading"
    with pytest.raises(ProviderError, match="verified"):
        build.publish()
    build.upload(provider)
    assert len(saved) == 25
    assert build.release["status"] == "uploaded"
    assert not (build.path / "published.json").exists()


def test_modified_artifact_rejected(prepared, tmp_path):
    settings, result = prepared
    alternate = settings.model_copy(update={"ingestion_artifact_root": tmp_path})
    prepare(alternate)
    path = tmp_path / "releases" / result["build_id"] / "search-records.jsonl"
    path.write_text("{}\n")
    with pytest.raises(ValueError, match="Modified release"):
        Build(alternate, result["build_id"])
    with pytest.raises(ValueError, match="version increment"):
        prepare(alternate)


def test_namespace_budget_stops_before_embedding(prepared):
    settings, result = prepared
    build = Build(settings, result["build_id"])
    target = build.release.get("target", {})
    provider = SimpleNamespace(
        preflight=lambda _: target,
        namespace_inventory=lambda: {f"old-{i}": {} for i in range(100)},
    )
    with pytest.raises(ProviderError, match="NAMESPACE_BUDGET"):
        build.preflight(provider)


def test_failed_reverification_invalidates_publication(prepared, monkeypatch):
    settings, result = prepared
    build = Build(settings, result["build_id"])
    build.release["status"] = "verified"
    (build.path / "published.json").write_text("{}")
    monkeypatch.setattr(build, "preflight", lambda _: None)
    with pytest.raises(ProviderError, match="Uploaded IDs"):
        build.verify(SimpleNamespace(list_ids=lambda _: set()), attempts=1)
    assert build.release["status"] == "verifying"
    assert not (build.path / "published.json").exists()
    with pytest.raises(ProviderError, match="verified"):
        build.publish()
