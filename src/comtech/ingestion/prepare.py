"""Lossless source hierarchy, bounded passages and extractive discovery summaries."""

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import tiktoken

VERSION = "northstar-ingestion-1"
TARGET, MAX_INPUT, OVERLAP = 400, 600, 50


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path, rows):
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()
    if path.exists() and path.read_bytes() != data:
        raise ValueError("Preparation changed without a pipeline version increment")
    path.write_bytes(data)


def encoding():
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(Path(".cache/tiktoken").resolve()))
    return tiktoken.get_encoding("cl100k_base")


def tokens(text):
    return len(encoding().encode(text, disallowed_special=()))


def bounded(text, budget):
    """A Unicode-safe prefix for context only. Source passages are never truncated."""
    if tokens(text) <= budget:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if tokens(text[:mid]) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]


def context(meta, heading):
    return (
        f"Document: {bounded(meta['title'], 45)}\nVersion: {meta['version']}\n"
        f"Section: {bounded(heading, 40)}\n"
        f"Services: {bounded(', '.join(meta['service_ids']), 25)}\n"
        f"Effective from: {meta['effective_from']}\n\n"
    )


def chunk_spans(text, prefix):
    """Contiguous exact character spans; prefer paragraphs, lines, then sentences."""
    if tokens(prefix + text) <= MAX_INPUT:
        return [(0, len(text))]
    spans, start = [], 0
    paragraph = [m.end() for m in re.finditer(r"\n\s*\n", text)]
    lines = [m.end() for m in re.finditer(r"\n", text)]
    sentences = [m.end() for m in re.finditer(r"[.!?](?:[\"')])?\s+", text)]
    while start < len(text):
        remainder = text[start:]
        if tokens(prefix + remainder) <= MAX_INPUT:
            end = len(text)
        else:
            cap = start + len(bounded(remainder, min(TARGET, MAX_INPUT - tokens(prefix) - 4)))
            end = cap
            for boundaries in (paragraph, lines, sentences):
                choices = [p for p in boundaries if start < p <= cap]
                if choices:
                    end = choices[-1]
                    break
            if spans and end <= spans[-1][1]:
                end = cap
        if end <= start or tokens(prefix + text[start:end]) > MAX_INPUT:
            raise ValueError("Unable to construct a bounded nonempty passage")
        spans.append((start, end))
        if end == len(text):
            break
        # Prefer whole-line/sentence overlap. Never let overlap prevent forward progress.
        candidates = sorted({p for p in lines + sentences if start < p < end})
        overlap_start = next((p for p in candidates if tokens(text[p:end]) <= OVERLAP), end)
        start = overlap_start if overlap_start > start else end
    return spans


def summary(source, sections):
    eligible = [
        s
        for s in sections
        if not re.search(
            r"untrusted|attachment|business and service context|review method|related records",
            s["section_heading"],
            re.I,
        )
    ]
    # Select across the full outline, including the end of long manuals.
    if len(eligible) > 8:
        eligible = [eligible[round(i * (len(eligible) - 1) / 7)] for i in range(8)]
    queues = []
    for section in eligible:
        a, b = section["char_start"], section["char_end"]
        candidates = []
        for match in re.finditer(r"\S[\s\S]*?(?:[.!?](?=\s|$)|$)", source[a:b]):
            left, right = a + match.start(), a + match.end()
            text = source[left:right]
            if text.strip() and not text.startswith((">", "<", "#")):
                candidates.append((left, right))
        queues.append(candidates)
    selected = []
    for rank in range(max((len(q) for q in queues), default=0)):
        for queue in queues:
            if rank >= len(queue):
                continue
            span = queue[rank]
            candidate = "\n".join(source[a:b] for a, b in selected + [span])
            if tokens(candidate) <= 350:
                selected.append(span)
        if tokens("\n".join(source[a:b] for a, b in selected)) >= 200:
            break
    if not selected:
        raise ValueError("No substantive summary sentences found")
    selected.sort()
    return "\n".join(source[a:b] for a, b in selected), [
        {"char_start": a, "char_end": b} for a, b in selected
    ]


def flat_metadata(meta):
    """Pinecone projection; full null/nested values remain in local manifests."""
    return {
        k: v
        for k, v in meta.items()
        if isinstance(v, (str, int, float, bool))
        or isinstance(v, list)
        and all(isinstance(x, str) for x in v)
    }


def prepare(settings):
    root = settings.ingestion_source_root.resolve()
    artifacts = settings.ingestion_artifact_root.resolve()
    manifest = sorted(read_jsonl(root / "manifest.jsonl"), key=lambda x: x["document_id"])
    config = {
        "pipeline_version": VERSION,
        "model": settings.openai_embedding_model,
        "dimensions": settings.openai_embedding_dimensions,
        "target": TARGET,
        "max_input": MAX_INPUT,
        "overlap": OVERLAP,
        "tokenizer": "cl100k_base",
    }
    build = digest({"config": config, "manifest": manifest})[:16]
    release = artifacts / "releases" / build
    release.mkdir(parents=True, exist_ok=True)
    by_id = {m["document_id"]: m for m in manifest}
    if len(by_id) != len(manifest):
        raise ValueError("Duplicate document IDs")
    documents, sections, passages, summaries, records = [], [], [], [], []
    for meta in manifest:
        path = (root.parent / meta["content_path"]).resolve()
        if not path.is_relative_to(root / "documents") or path.suffix != ".md":
            raise ValueError("Source path escapes public corpus documents")
        raw = path.read_bytes()
        if digest(raw) != meta["sha256"]:
            raise ValueError(f"Source hash mismatch: {meta['document_id']}")
        source = raw.decode("utf-8")
        locator = f"source-store/sha256/{digest(raw)}.md"
        stored = artifacts / locator
        stored.parent.mkdir(parents=True, exist_ok=True)
        if stored.exists() and stored.read_bytes() != raw:
            raise ValueError("Content-addressed source store is corrupt")
        stored.write_bytes(raw)
        family, seen = meta["document_id"], set()
        while by_id[family].get("supersedes_document_id"):
            if family in seen:
                raise ValueError("Cyclic supersession")
            seen.add(family)
            family = by_id[family]["supersedes_document_id"]
        base = {k: v for k, v in meta.items() if k not in ("sections", "namespace")}
        base.update(
            build_id=build,
            document_family_id=family,
            source_locator=locator,
            source_sha256=digest(raw),
            pipeline_version=VERSION,
            embedding_model=config["model"],
            embedding_dimensions=config["dimensions"],
            namespace=f"northstar-{build}-{meta['corpus']}",
        )
        doc = {**base, "outline": meta["sections"], "section_ids": []}
        lines = source.splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        doc_sections = []
        for section in meta["sections"]:
            a, b = offsets[section["line_start"] - 1], offsets[section["line_end"]]
            while b > a and source[b - 1].isspace():
                b -= 1
            section_id = f"{meta['document_id']}:v{meta['version']}:{section['anchor']}"
            s = {
                **base,
                **section,
                "section_id": section_id,
                "char_start": a,
                "char_end": b,
                "passage_ids": [],
            }
            doc["section_ids"].append(section_id)
            doc_sections.append(s)
            prefix = context(meta, section["section_heading"])
            local = []
            for ordinal, (left, right) in enumerate(chunk_spans(source[a:b], prefix), 1):
                text = source[a + left : a + right]
                passage = {
                    **s,
                    "record_id": f"{section_id}:p{ordinal:04}",
                    "record_type": "passage",
                    "passage_ordinal": ordinal,
                    "char_start": a + left,
                    "char_end": a + right,
                    "line_start": source.count("\n", 0, a + left) + 1,
                    "line_end": source.count("\n", 0, a + right - 1) + 1,
                    "source_text": text,
                    "heading_text": section["section_heading"],
                    "search_text": prefix + text,
                }
                passage.pop("passage_ids")
                local.append(passage)
                s["passage_ids"].append(passage["record_id"])
            for i, passage in enumerate(local):
                passage["previous_passage_id"] = local[i - 1]["record_id"] if i else None
                passage["next_passage_id"] = (
                    local[i + 1]["record_id"] if i + 1 < len(local) else None
                )
            passages.extend(local)
        text, provenance = summary(source, doc_sections)
        outline = " | ".join(s["section_heading"] for s in doc_sections)
        summaries.append(
            {
                **base,
                "record_id": f"{meta['document_id']}:v{meta['version']}:summary",
                "record_type": "document_summary",
                "summary_text": text,
                "summary_algorithm": VERSION + "-extractive",
                "summary_spans": provenance,
                "heading_text": bounded(outline, 160),
                "search_text": context(meta, "Document summary") + text,
            }
        )
        documents.append(doc)
        sections.extend(doc_sections)
    for item in passages + summaries:
        count = tokens(item["search_text"])
        if not 0 < count <= MAX_INPUT:
            raise ValueError("Invalid embedding input size")
        item["embedding_input_sha256"] = digest(item["search_text"].encode())
        item["embedding_cache_key"] = digest({"input": item["search_text"], **config})
        item["embedding_tokens"] = count
        records.append(flat_metadata(item))
    for name, rows in (
        ("documents", documents),
        ("sections", sections),
        ("passages", passages),
        ("summaries", summaries),
        ("search-records", records),
    ):
        path = release / f"{name}.jsonl"
        # A deterministic prepare rerun cannot discard online stage state.
        write_jsonl(path, rows)
    hashes = {p.name: digest(p.read_bytes()) for p in release.glob("*.jsonl")}
    result = {
        "build_id": build,
        "status": "prepared",
        "config": config,
        "counts": {
            "documents": len(documents),
            "sections": len(sections),
            "passages": len(passages),
            "summaries": len(summaries),
            "search_records": len(records),
        },
        "namespaces": dict(Counter(r["namespace"] for r in records)),
        "embedding_tokens": sum(r["embedding_tokens"] for r in records),
        "artifact_sha256": hashes,
    }
    existing = release / "release.json"
    if existing.exists():
        old = json.loads(existing.read_text(encoding="utf-8"))
        if old["artifact_sha256"] != hashes:
            raise ValueError("Preparation changed without a pipeline version increment")
    else:
        write_json(existing, result)
    return result
