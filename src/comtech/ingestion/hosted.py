"""Resumable ingestion through Pinecone Documents API 2026-07 and OpenAI."""

import json
import math
import re
import ssl
import time
from collections import defaultdict
from datetime import UTC, datetime
from urllib.parse import quote, urlparse

import httpx
from openai import OpenAI

from .prepare import digest, read_jsonl, write_json

API_VERSION = "2026-07"


class ProviderError(RuntimeError):
    """Safe provider failure without credentials, headers, or source text."""


def schema(dimensions):
    return {
        "fields": {
            **{
                name: {"type": "string", "full_text_search": {"language": "en"}}
                for name in ("title", "heading_text", "search_text")
            },
            "embedding": {"type": "dense_vector", "dimension": dimensions, "metric": "cosine"},
        }
    }


def validate_schema(actual, expected):
    fields = actual.get("fields", {})
    for name, field in expected["fields"].items():
        found = fields.get(name, {})
        for key, value in field.items():
            if key == "full_text_search":
                if not isinstance(found.get(key), dict) or found[key].get("language", "en") != "en":
                    raise ProviderError(f"Incompatible BM25 schema: {name}")
            elif found.get(key) != value:
                raise ProviderError(f"Incompatible index field: {name}/{key}")


class PineconeDocuments:
    def __init__(self, settings, client=None):
        key = settings.pinecone_api_key.get_secret_value()
        if not key:
            raise ProviderError("PINECONE_API_KEY is missing")
        if settings.pinecone_mode != "hosted":
            raise ProviderError("This ingestion requires hosted Pinecone")
        self.settings = settings
        self.client = client or httpx.Client(verify=ssl.create_default_context(), timeout=60)
        self.headers = {"Api-Key": key, "X-Pinecone-Api-Version": API_VERSION}
        self.host = None

    def close(self):
        self.client.close()

    def request(self, method, url, **kwargs):
        for attempt in range(5):
            try:
                response = self.client.request(method, url, headers=self.headers, **kwargs)
            except httpx.TransportError:
                if attempt == 4:
                    raise ProviderError("Pinecone connection failed after retries") from None
                time.sleep(min(2**attempt, 16))
                continue
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(min(2**attempt, 16))
                continue
            return response
        raise ProviderError("Pinecone retries exhausted")

    @staticmethod
    def checked(response):
        if not response.is_success:
            # Never echo provider bodies: they may contain submitted text or secrets.
            raise ProviderError(
                f"Pinecone HTTP {response.status_code}; "
                "check account access, quota, region and Documents API support"
            )
        return response.json()

    def preflight(self, dimensions):
        name = self.settings.pinecone_index_name
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,44}", name):
            raise ProviderError("Invalid PINECONE_INDEX_NAME")
        url = "https://api.pinecone.io/indexes/" + name
        response = self.request("GET", url)
        wanted = schema(dimensions)
        if response.status_code == 404:
            self.checked(
                self.request(
                    "POST",
                    "https://api.pinecone.io/indexes",
                    json={
                        "name": name,
                        "deployment": {
                            "deployment_type": "managed",
                            "cloud": self.settings.pinecone_cloud,
                            "region": self.settings.pinecone_region,
                        },
                        "schema": wanted,
                    },
                )
            )
        else:
            self.checked(response)
        for _ in range(60):
            info = self.checked(self.request("GET", url))
            validate_schema(info.get("schema", {}), wanted)
            if info.get("status", {}).get("ready"):
                break
            time.sleep(3)
        else:
            raise ProviderError("Index readiness timed out")
        host = info["host"]
        parsed = urlparse(host if "://" in host else "https://" + host)
        if parsed.scheme != "https" or not parsed.hostname.endswith(".pinecone.io"):
            raise ProviderError("Unexpected Pinecone data host")
        self.host = parsed.geturl().rstrip("/")
        configured = self.settings.pinecone_index_host.rstrip("/").removeprefix("https://")
        if configured and configured != parsed.netloc:
            raise ProviderError("Configured host differs from resolved index host")
        return {"index_name": name, "host": self.host, "schema": wanted, "api_version": API_VERSION}

    def data(self, namespace, operation, payload):
        if not self.host:
            raise ProviderError("Preflight is required")
        url = f"{self.host}/namespaces/{quote(namespace, safe='')}/documents/{operation}"
        return self.checked(self.request("POST", url, json=payload))

    def list_ids(self, namespace):
        result, payload, seen = set(), {"limit": 100}, set()
        while True:
            page = self.data(namespace, "list", payload)
            result.update(d["_id"] for d in page.get("documents", []))
            token = page.get("pagination", {}).get("next")
            if not token:
                return result
            if token in seen:
                raise ProviderError("Repeated Pinecone pagination token")
            seen.add(token)
            payload["pagination_token"] = token

    def namespace_inventory(self):
        result, params, seen = {}, {"limit": 100}, set()
        while True:
            page = self.checked(self.request("GET", self.host + "/namespaces", params=params))
            result.update({n["name"]: n for n in page.get("namespaces", [])})
            token = page.get("pagination", {}).get("next")
            if not token:
                return result
            if token in seen:
                raise ProviderError("Repeated namespace pagination token")
            seen.add(token)
            params["pagination_token"] = token


def vector_valid(vector, dimensions):
    return (
        isinstance(vector, list)
        and len(vector) == dimensions
        and all(
            isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
            for v in vector
        )
        and any(vector)
    )


class Build:
    def __init__(self, settings, build_id):
        if not re.fullmatch(r"[a-f0-9]{16}", build_id):
            raise ValueError("Invalid build ID")
        self.settings = settings
        self.root = settings.ingestion_artifact_root.resolve()
        self.path = self.root / "releases" / build_id
        self.release = json.loads((self.path / "release.json").read_text(encoding="utf-8"))
        for name, expected in self.release["artifact_sha256"].items():
            if digest((self.path / name).read_bytes()) != expected:
                raise ValueError(f"Modified release artifact: {name}")
        config = self.release["config"]
        if (config["model"], config["dimensions"]) != (
            settings.openai_embedding_model,
            settings.openai_embedding_dimensions,
        ):
            raise ValueError("Settings differ from build embedding configuration")
        self.records = read_jsonl(self.path / "search-records.jsonl")
        self.dimensions = config["dimensions"]
        self.cache = self.root / "cache" / "embeddings"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.log = self.root / "runs" / build_id / "progress.jsonl"
        self.log.parent.mkdir(parents=True, exist_ok=True)

    def event(self, stage, **fields):
        event = {"at": datetime.now(UTC).isoformat(), "stage": stage, **fields}
        with self.log.open("a", encoding="utf-8") as out:
            out.write(json.dumps(event) + "\n")
        print(json.dumps(event), flush=True)

    def save(self):
        write_json(self.path / "release.json", self.release)

    def preflight(self, pinecone):
        target = pinecone.preflight(self.dimensions)
        previous = self.release.get("target")
        if previous and previous != target:
            raise ProviderError("Release target changed; prepare a separate release")
        inventory = pinecone.namespace_inventory()
        proposed = set(self.release["namespaces"])
        total = len(set(inventory) | proposed)
        if total > self.settings.pinecone_namespace_budget:
            raise ProviderError(
                "Proposed build exceeds PINECONE_NAMESPACE_BUDGET; "
                "review account limits before increasing this setting"
            )
        self.release["namespace_preflight"] = {
            "existing": len(inventory),
            "new": len(proposed - set(inventory)),
            "combined": total,
            "configured_budget": self.settings.pinecone_namespace_budget,
            "observed_size_bytes": sum(int(n.get("size_bytes", 0)) for n in inventory.values()),
        }
        self.release["target"] = target
        self.save()
        self.event("preflight", index=target["index_name"], status="ready")

    def cached(self, record):
        path = self.cache / (record["embedding_cache_key"] + ".json")
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("key") != record["embedding_cache_key"] or not vector_valid(
            value.get("vector"), self.dimensions
        ):
            raise ValueError("Invalid cached embedding")
        return value["vector"]

    def embed(self, client=None):
        if not self.release.get("target"):
            raise ProviderError("Run Pinecone preflight before embedding")
        key = self.settings.openai_api_key.get_secret_value()
        if not key:
            raise ProviderError("OPENAI_API_KEY is missing")
        own_client = client is None
        client = client or OpenAI(
            api_key=key,
            max_retries=4,
            timeout=60,
            http_client=httpx.Client(verify=ssl.create_default_context()),
        )
        pending = [r for r in self.records if self.cached(r) is None]
        self.event("embed_start", cached=len(self.records) - len(pending), pending=len(pending))
        billed = 0
        try:
            # 64 inputs, each <=600 tokens, also bounded to 12k tokens per request.
            batch, batch_tokens = [], 0
            batches = []
            for record in pending:
                if batch and (
                    len(batch) >= 64 or batch_tokens + record["embedding_tokens"] > 12000
                ):
                    batches.append(batch)
                    batch, batch_tokens = [], 0
                batch.append(record)
                batch_tokens += record["embedding_tokens"]
            if batch:
                batches.append(batch)
            for batch in batches:
                response = client.embeddings.create(
                    model=self.release["config"]["model"],
                    dimensions=self.dimensions,
                    input=[r["search_text"] for r in batch],
                    encoding_format="float",
                )
                mapped = {item.index: item.embedding for item in response.data}
                if set(mapped) != set(range(len(batch))) or len(response.data) != len(batch):
                    raise ProviderError("Embedding response indices do not match inputs")
                for index, record in enumerate(batch):
                    vector = mapped[index]
                    if not vector_valid(vector, self.dimensions):
                        raise ProviderError("Invalid embedding vector")
                    write_json(
                        self.cache / (record["embedding_cache_key"] + ".json"),
                        {
                            "key": record["embedding_cache_key"],
                            "model": response.model,
                            "dimensions": self.dimensions,
                            "vector": vector,
                        },
                    )
                billed += response.usage.total_tokens
                self.release["embedding_usage_tokens"] = (
                    self.release.get("embedding_usage_tokens", 0) + response.usage.total_tokens
                )
                self.save()
                self.event(
                    "embedding_batch", records=len(batch), tokens=response.usage.total_tokens
                )
        finally:
            if own_client:
                client.close()
        self.release["embeddings_complete"] = True
        self.save()
        return {
            "embedded": len(pending),
            "cache_hits": len(self.records) - len(pending),
            "usage_tokens": billed,
        }

    def upload(self, pinecone):
        self.preflight(pinecone)
        self.verify_sources()
        self.release["status"] = "uploading"
        self.save()
        # Re-uploading invalidates the previously published handoff until verified again.
        (self.path / "published.json").unlink(missing_ok=True)
        groups = defaultdict(list)
        for record in self.records:
            vector = self.cached(record)
            if vector is None:
                raise ProviderError("Missing embeddings; run embed before upload")
            doc = {k: v for k, v in record.items() if k != "namespace"}
            doc.update(_id=record["record_id"], embedding=vector)
            if len(json.dumps(doc).encode()) > 100_000:
                raise ValueError("Oversized search record")
            groups[record["namespace"]].append(doc)
        # Deterministic IDs make whole-stage retries safe after interrupted requests.
        for namespace, docs in groups.items():
            for start in range(0, len(docs), 20):
                batch = docs[start : start + 20]
                response = pinecone.data(namespace, "upsert", {"documents": batch})
                if response.get("upserted_count") != len(batch):
                    raise ProviderError("Unexpected upsert count")
                self.event("upload_batch", namespace=namespace, records=len(batch))
        self.release["status"] = "uploaded"
        self.save()

    def verify_sources(self):
        sources = {}
        for doc in read_jsonl(self.path / "documents.jsonl"):
            path = (self.root / doc["source_locator"]).resolve()
            if not path.is_relative_to(self.root / "source-store"):
                raise ValueError("Unsafe source locator")
            raw = path.read_bytes()
            if digest(raw) != doc["source_sha256"]:
                raise ValueError("Source store hash mismatch")
            sources[doc["document_id"]] = raw.decode()
        for p in read_jsonl(self.path / "passages.jsonl"):
            if sources[p["document_id"]][p["char_start"] : p["char_end"]] != p["source_text"]:
                raise ValueError("Passage source span mismatch")
        for s in read_jsonl(self.path / "summaries.jsonl"):
            source = sources[s["document_id"]]
            if (
                "\n".join(source[p["char_start"] : p["char_end"]] for p in s["summary_spans"])
                != s["summary_text"]
            ):
                raise ValueError("Summary source span mismatch")

    def verify(self, pinecone, attempts=24):
        self.preflight(pinecone)
        self.release["status"] = "verifying"
        self.save()
        (self.path / "published.json").unlink(missing_ok=True)
        self.verify_sources()
        groups = defaultdict(list)
        for record in self.records:
            groups[record["namespace"]].append(record)
        results = {}
        for namespace, records in groups.items():
            expected = {r["record_id"] for r in records}
            for attempt in range(attempts):
                found = pinecone.list_ids(namespace)
                if found == expected:
                    break
                if attempt + 1 == attempts:
                    raise ProviderError("Uploaded IDs differ from expected release IDs")
                time.sleep(5)
            # Reconcile all metadata and vectors, not just aggregate counts.
            for start in range(0, len(records), 20):
                batch = records[start : start + 20]
                fetched = pinecone.data(
                    namespace,
                    "fetch",
                    {
                        "ids": [r["record_id"] for r in batch],
                        "include_fields": ["*"],
                    },
                )["documents"]
                for record in batch:
                    item = fetched.get(record["record_id"], {})
                    for k, v in record.items():
                        if k != "namespace" and item.get(k) != v:
                            raise ProviderError(f"Fetched field mismatch: {k}")
                    actual, wanted = item.get("embedding"), self.cached(record)
                    if not vector_valid(actual, self.dimensions) or any(
                        not math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-7)
                        for a, b in zip(actual, wanted, strict=True)
                    ):
                        raise ProviderError("Fetched vector differs from cached embedding")
            sample = records[0]
            probes = [
                {"type": "text", "fields": ["search_text"], "query": sample["title"]},
                {"type": "dense_vector", "fields": ["embedding"], "values": self.cached(sample)},
            ]
            for probe in probes:
                for attempt in range(attempts):
                    response = pinecone.data(
                        namespace,
                        "search",
                        {
                            "score_by": [probe],
                            "top_k": 3,
                            "filter": {"record_id": {"$eq": sample["record_id"]}},
                            "include_fields": ["record_id"],
                        },
                    )
                    if any(m["_id"] == sample["record_id"] for m in response.get("matches", [])):
                        break
                    if attempt + 1 == attempts:
                        raise ProviderError("Search capability probe failed")
                    time.sleep(5)
            results[namespace] = {
                "records": len(records),
                "metadata_and_vectors": "passed",
                "bm25": "passed",
                "dense": "passed",
            }
            self.event("verified_namespace", namespace=namespace, records=len(records))
        report = {
            "status": "passed",
            "build_id": self.release["build_id"],
            "verified_at": datetime.now(UTC).isoformat(),
            "namespaces": results,
            "source_spans": "passed",
            "scope": "Ingestion integrity, not retrieval quality",
        }
        write_json(self.path / "verification.json", report)
        self.release["status"] = "verified"
        self.save()
        return report

    def publish(self):
        if self.release["status"] != "verified":
            raise ProviderError("Only verified releases can be published")
        self.verify_sources()
        report = json.loads((self.path / "verification.json").read_text(encoding="utf-8"))
        if report["status"] != "passed" or report["build_id"] != self.release["build_id"]:
            raise ProviderError("Missing matching verification")
        write_json(
            self.path / "published.json",
            {
                **self.release,
                "published_at": datetime.now(UTC).isoformat(),
                "verification_sha256": digest((self.path / "verification.json").read_bytes()),
                "source_store_required": True,
            },
        )
        self.event("published", build=self.release["build_id"])
