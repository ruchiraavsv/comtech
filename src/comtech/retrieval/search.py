"""Hybrid document discovery against the pinned Pinecone Documents release."""

import asyncio
import ssl
from datetime import date
from urllib.parse import quote, urlparse

import httpx

from comtech.agents.contracts import ToolResult
from comtech.research.accounting import source_call
from comtech.retrieval.embedding import QueryEmbedding
from comtech.retrieval.store import observation


class HybridSearch:
    def __init__(self, store, settings, embeddings, counter, http=None, *, embed_query=None):
        self.store, self.counter = store, counter
        config = store.manifest["config"]
        self.embed_query = embed_query or QueryEmbedding(
            embeddings, counter, model=config["model"], dimensions=config["dimensions"]
        )
        self.key = settings.pinecone_api_key.get_secret_value()
        self.host = store.manifest["target"]["host"].rstrip("/")
        parsed = urlparse(self.host)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".pinecone.io"):
            raise ValueError("Invalid published Pinecone host")
        if not self.key:
            raise ValueError("PINECONE_API_KEY is required")
        self.http = http or httpx.AsyncClient(timeout=15, verify=ssl.create_default_context())
        self.semaphore = asyncio.Semaphore(4)

    async def close(self):
        await self.http.aclose()

    def eligible(self, args):
        after = date.fromisoformat(args.created_after) if args.created_after else None
        before = date.fromisoformat(args.created_before) if args.created_before else None
        if after and before and after > before:
            raise ValueError("Invalid date interval")
        result = []
        for doc in self.store.documents.values():
            created = date.fromisoformat(doc["created_at"][:10])
            if args.document_types and doc["document_type"] not in args.document_types:
                continue
            if args.departments and doc["department"] not in args.departments:
                continue
            if args.service_ids and not set(args.service_ids).intersection(doc["service_ids"]):
                continue
            if after and created < after or before and created > before:
                continue
            result.append(doc["document_id"])
        return result

    async def search(self, args, *, allowed_ids=None):
        if not args.query.strip():
            raise ValueError("Query cannot be blank")
        eligible = self.eligible(args)
        if allowed_ids is not None:
            eligible = [key for key in eligible if key in allowed_ids]
        if not eligible:
            return ToolResult(details="No document metadata matched the requested filters.")
        vector = await self.embed_query(args.query)
        predicate = {"document_id": {"$in": eligible}}
        branches = [
            {"type": "text", "fields": ["search_text"], "query": args.query},
            {"type": "dense_vector", "fields": ["embedding"], "values": vector},
        ]

        async def query(namespace, score_by):
            async with self.semaphore:
                url = f"{self.host}/namespaces/{quote(namespace, safe='')}/documents/search"
                response = await source_call(
                    lambda: self.http.post(
                        url,
                        headers={
                            "Api-Key": self.key,
                            "X-Pinecone-Api-Version": "2026-07",
                        },
                        json={
                            "score_by": [score_by],
                            "top_k": args.top_k,
                            "filter": predicate,
                            "include_fields": ["record_id"],
                        },
                    )
                )
                if not response.is_success:
                    raise RuntimeError(f"Search provider HTTP {response.status_code}")
                if len(response.content) > 1_000_000:
                    raise RuntimeError("Search response exceeds transport limit")
                return response.json().get("matches", [])

        lists = await asyncio.gather(
            *(query(ns, branch) for ns in self.store.manifest["namespaces"] for branch in branches),
            return_exceptions=True,
        )
        for item in lists:
            if isinstance(item, BaseException):
                raise item
        scores = {}
        for matches in lists:
            for rank, match in enumerate(matches):
                record_id = match["_id"]
                scores[record_id] = scores.get(record_id, 0) + 1 / (60 + rank + 1)
        observations, seen, rankings = [], set(), []
        for record_id in sorted(scores, key=lambda rid: (-scores[rid], rid)):
            row = self.store.passages.get(record_id) or self.store.summaries.get(record_id)
            if row is None or row["document_id"] not in eligible:
                raise RuntimeError("Search returned a record outside the pinned filtered release")
            if row["document_id"] in seen:
                continue
            seen.add(row["document_id"])
            if "source_text" in row:
                start, end = row["char_start"], row["char_end"]
            else:
                # One exact extractive span, not an uncited synthetic summary.
                span = row["summary_spans"][0]
                start, end = span["char_start"], span["char_end"]
            text = self.counter.prefix(self.store.sources[row["document_id"]][start:end], 180)
            item = observation(
                self.store.ref(row, start, start + len(text)),
                row["title"],
                text,
                effective_from=row.get("effective_from"),
                effective_to=row.get("effective_to"),
                is_partial=True,
            )
            proposed = ToolResult(observations=[*observations, item], details="Discovery snippets.")
            if self.counter.count(proposed) > 2800:
                break
            observations.append(item)
            rankings.append({"observation_id": item.observation_id, "score": scores[record_id]})
            if len(observations) >= args.top_k:
                break
        # Scores are discovery metadata; never source evidence.
        from comtech.agents.budget import serialized

        result = ToolResult(
            observations=observations,
            details=serialized(
                {"rankings": rankings, "coverage": "Bounded discovery; not exhaustive."}
            ),
        )
        while self.counter.count(result) > 3000 and result.observations:
            result.observations.pop()
            rankings.pop()
            result.details = serialized({"rankings": rankings, "coverage": "Bounded discovery."})
        return result
