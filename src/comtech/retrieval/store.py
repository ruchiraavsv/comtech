"""Read only published artifacts; return exact, bounded source observations."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from comtech.agents.budget import digest, serialized
from comtech.agents.contracts import (
    Contract,
    Observation,
    ReadDocumentSectionsResult,
    SourceRef,
)


class ReadArgs(Contract):
    document_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=1000)
    section_ids: list[str] | None = Field(
        default=None,
        description=(
            "Exact IDs returned by this document's observations or section_options; "
            "null ranks by query. Never guess IDs."
        ),
    )
    max_sections: int = Field(default=3, ge=1, le=10)

    @classmethod
    def for_limits(cls, arguments, limits):
        args = cls.model_validate(arguments)
        if "max_sections" not in args.model_fields_set:
            args.max_sections = min(3, limits.max_sections_per_read)
        return args


class DocumentArgumentError(ValueError):
    """Safe correction guidance, containing no source text or private paths."""


class SearchArgs(Contract):
    query: str = Field(min_length=1, max_length=1000)
    document_types: list[str] | None = None
    departments: list[str] | None = None
    service_ids: list[str] | None = None
    created_after: str | None = None
    created_before: str | None = None
    top_k: int = Field(default=8, ge=1, le=12)


def words(text):
    return set(re.findall(r"\w+", text.casefold()))


def observation(ref, title, content, **metadata):
    identity = serialized([ref, content])
    return Observation(
        observation_id="OBS-" + digest(identity)[:24],
        source_ref=ref,
        title=title,
        content=content,
        content_hash=digest(content),
        retrieved_at=datetime.now(UTC).isoformat(),
        **metadata,
    )


class SourceStore:
    def __init__(self, root, build_id):
        if not re.fullmatch(r"[a-f0-9]{16}", build_id):
            raise ValueError("Invalid published build ID")
        self.root = Path(root).resolve()
        release = self.root / "releases" / build_id
        self.manifest = json.loads((release / "published.json").read_text(encoding="utf-8"))
        if self.manifest.get("build_id") != build_id:
            raise ValueError("Published release identity mismatch")
        if self.manifest.get("status") != "verified" or not self.manifest.get(
            "source_store_required"
        ):
            raise ValueError("A verified source-store release is required")
        verification = (release / "verification.json").read_bytes().decode("utf-8")
        if digest(verification) != self.manifest.get("verification_sha256"):
            raise ValueError("Published verification checksum mismatch")
        self.build_id = build_id
        for name, expected in self.manifest["artifact_sha256"].items():
            path = (release / name).resolve()
            if path.parent != release or digest(path.read_bytes().decode("utf-8")) != expected:
                raise ValueError("Release artifact checksum/path mismatch")

        def load(name, key):
            rows = [
                json.loads(line)
                for line in (release / name).read_text(encoding="utf-8").splitlines()
                if line
            ]
            indexed = {row[key]: row for row in rows}
            if len(indexed) != len(rows):
                raise ValueError("Duplicate source identity")
            return indexed

        self.documents = load("documents.jsonl", "document_id")
        self.sections = load("sections.jsonl", "section_id")
        self.passages = load("passages.jsonl", "record_id")
        self.summaries = load("summaries.jsonl", "record_id")
        self.sources = {}
        for doc_id, doc in self.documents.items():
            path = (self.root / doc["source_locator"]).resolve()
            if not path.is_relative_to(self.root / "source-store"):
                raise ValueError("Source path escapes source store")
            source = path.read_bytes().decode("utf-8")
            if digest(source) != doc["source_sha256"]:
                raise ValueError("Source hash mismatch")
            self.sources[doc_id] = source
        for section in self.sections.values():
            source = self.sources[section["document_id"]]
            if not 0 <= section["char_start"] < section["char_end"] <= len(source):
                raise ValueError("Invalid section span")
        for passage in self.passages.values():
            source = self.sources[passage["document_id"]]
            if source[passage["char_start"] : passage["char_end"]] != passage["source_text"]:
                raise ValueError("Passage source mismatch")

    def ref(self, row, start=None, end=None):
        return SourceRef(
            source_type="document",
            source_id=row["document_id"],
            version=str(row["version"]),
            section_id=row.get("section_id"),
            record_id=row.get("record_id"),
            char_start=start,
            char_end=end,
        )

    def resolve_document_id(self, selector):
        """Resolve only exact manifest IDs or their unambiguous DOC- shorthand."""
        if selector in self.documents:
            return selector
        canonical = "DOC-" + selector
        if canonical in self.documents:
            return canonical
        raise DocumentArgumentError(
            "Unknown document selector. Discover its exact document_id with knowledge_search; "
            "do not invent an ID or narrow scope to an unverified name."
        )

    def excerpt(self, section, query, counter, limit):
        source = self.sources[section["document_id"]]
        a, b = section["char_start"], section["char_end"]
        # Query-ranked paragraph windows allow repeated navigation inside large sections.
        starts = [a] + [a + m.end() for m in re.finditer(r"\n\s*\n", source[a:b])]
        query_words = words(query)
        starts.sort(key=lambda p: (-len(query_words & words(source[p : min(b, p + 4000)])), p))
        start = starts[0]
        # Also consider query occurrences for oversized single paragraphs.
        if counter.text(source[a:b]) > limit:
            positions = (
                [
                    max(a, a + m.start() - 120)
                    for m in re.finditer(
                        "|".join(re.escape(w) for w in sorted(query_words)), source[a:b], re.I
                    )
                ]
                if query_words
                else []
            )
            if positions:
                start = max(
                    [start, *positions],
                    key=lambda p: (len(query_words & words(source[p : min(b, p + 2500)])), -p),
                )
        else:
            start = a
        content = counter.prefix(source[start:b], limit)
        end = start + len(content)
        return observation(
            self.ref(section, start, end),
            section["section_heading"],
            content,
            effective_from=section.get("effective_from"),
            effective_to=section.get("effective_to"),
            is_partial=start != a or end != b,
            token_count=counter.text(content),
            remaining_spans=[
                (left, right) for left, right in ((a, start), (end, b)) if left < right
            ],
        )

    def read(self, args, counter, limits):
        if not args.query.strip():
            raise DocumentArgumentError("query must contain a nonblank search phrase.")
        if args.max_sections > limits.max_sections_per_read:
            raise DocumentArgumentError(
                f"max_sections must be between 1 and {limits.max_sections_per_read}. "
                "Use a targeted query or returned section_options IDs for a necessary follow-up."
            )
        if args.document_id not in self.documents:
            raise KeyError("Document not found")
        doc = self.documents[args.document_id]
        ids = args.section_ids
        if ids is not None and (
            not ids
            or len(ids) > args.max_sections
            or len(set(ids)) != len(ids)
            or any(s not in doc["section_ids"] for s in ids)
        ):
            raise DocumentArgumentError(
                "section_ids must be unique exact IDs from this document/version, with count "
                "no greater than max_sections. Use section_ids=null with a targeted query "
                "to discover valid IDs in observations and section_options."
            )
        candidates = [self.sections[s] for s in (ids or doc["section_ids"])]
        query_words = words(args.query)

        def rank(section):
            return (
                -len(query_words & words(section["section_heading"])) * 3
                - len(
                    query_words
                    & words(
                        self.sources[args.document_id][section["char_start"] : section["char_end"]]
                    )
                ),
                section["section_ordinal"],
            )

        if ids is None:
            candidates.sort(key=rank)
            candidates = candidates[: args.max_sections]
        result = ReadDocumentSectionsResult(
            document_id=args.document_id,
            version=str(doc["version"]),
            details="Only returned spans were inspected; other content is unread.",
            omitted_sections=len(candidates) < len(doc["section_ids"]),
        )
        for section in candidates:
            cap = limits.max_tokens_per_section
            while cap >= 32:
                item = self.excerpt(section, args.query, counter, cap)
                proposed = result.model_copy(update={"observations": [*result.observations, item]})
                # Leave space for count/coverage values finalized below.
                if counter.count(proposed) + 12 <= limits.max_tokens_per_read:
                    result = proposed
                    break
                cap -= 32
        result.omitted_sections |= len(result.observations) < len(candidates)
        inspected = {o.source_ref.section_id for o in result.observations}
        remaining = sorted(
            (self.sections[s] for s in doc["section_ids"] if s not in inspected), key=rank
        )
        # Navigation metadata is not inspected evidence. Fit it in the existing read cap;
        # never discard exact source spans to make room for a directory.
        result.section_options_truncated = bool(remaining)
        for section in remaining[:8]:
            option = {"section_id": section["section_id"], "title": section["section_heading"]}
            proposed = result.model_copy(
                update={"section_options": [*result.section_options, option]}
            )
            if counter.count(proposed) + 12 > limits.max_tokens_per_read:
                break
            result = proposed
        result.section_options_truncated = len(result.section_options) < len(remaining)
        for _ in range(4):
            result.token_count = counter.count(result)
        return result
