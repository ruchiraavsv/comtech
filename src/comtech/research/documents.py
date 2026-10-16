"""Published document population and exact-span reads; never use ranked hits as a census."""

from datetime import UTC, datetime

from comtech.agents.budget import digest, serialized
from comtech.retrieval.store import observation

from .broker_contracts import DOCUMENT_FIELDS, MAX_PAGE_BYTES, BrokerError


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


class Documents:
    def __init__(self, store, records):
        self.store, self.records = store, records

    def eligible(self, scope):
        if scope.pinned_versions.get("documents") != self.store.build_id:
            raise BrokerError("SOURCE_VERSION", "Pinned document release is unavailable")
        if "documents" not in scope.datasets.get("documents", []):
            raise BrokerError("SCOPE_DENIED", "Document dataset is not allowed")
        rows = [
            r
            for r in self.store.documents.values()
            if scope.document_ids is None or r["document_id"] in scope.document_ids
        ]
        if scope.time_start:
            rows = [r for r in rows if instant(r["created_at"]) >= scope.time_start]
        if scope.time_end:
            rows = [r for r in rows if instant(r["created_at"]) <= scope.time_end]
        return self.versions(rows, scope.document_version_policy)

    @staticmethod
    def versions(rows, policy):
        if policy == "latest_in_release":
            newest = {}
            for row in rows:
                family = row.get("document_family_id", row["document_id"])
                rank = (int(row["version"]), row["created_at"], row["document_id"])
                if family not in newest or rank > newest[family][0]:
                    newest[family] = (rank, row)
            rows = [v[1] for v in newest.values()]
        return sorted(rows, key=lambda r: (r["document_id"], str(r["version"])))

    def require_fields(self, scope, fields):
        if not set(fields) <= set(scope.fields.get("documents", [])):
            raise BrokerError("SCOPE_DENIED", "Requested document fields are not allowed")

    def require_observation_fields(self, scope):
        # Observations include these metadata values alongside their exact source identity.
        self.require_fields(scope, ["content", "title", "effective_from", "effective_to"])

    def description(self, access, args):
        if args.source != "documents" or args.dataset not in (None, "documents"):
            raise BrokerError("CAPABILITY_UNAVAILABLE", "Dataset is unavailable")
        rows = self.eligible(access.scope)
        return {
            "schema_version": 1,
            "source": "documents",
            "dataset": "documents",
            "release": self.store.build_id,
            "primary_key": ["document_id", "version"],
            "fields": [f for f in DOCUMENT_FIELDS if f in access.scope.fields.get("documents", [])],
            "field_types": {
                f: (
                    "integer"
                    if f == "version"
                    else "array[string]"
                    if f == "service_ids"
                    else "string|null"
                )
                for f in DOCUMENT_FIELDS
                if f in access.scope.fields.get("documents", [])
            },
            "operations": access.scope.capabilities,
            "unavailable": ["lookup", "query"],
            "total_count": len(rows),
            "count_unit": "published document versions",
            "version_policy": access.scope.document_version_policy,
            "population_hash": self.population_hash(rows),
            "population_complete": True,
            "null_semantics": "Missing metadata is unknown, not zero or an inferred date.",
            "limits": {"page_rows": 1000, "page_bytes": MAX_PAGE_BYTES, "search_hits": 12},
            "relationships": [
                {"field": "document_family_id", "meaning": "Version family, not incident identity"}
            ],
        }

    def population_hash(self, rows):
        return digest(
            serialized(
                [
                    self.store.build_id,
                    [(r["document_id"], r["version"], r["source_sha256"]) for r in rows],
                ]
            )
        )

    async def enumerate(self, access, args):
        if not set(args.fields) <= set(DOCUMENT_FIELDS) or len(set(args.fields)) != len(
            args.fields
        ):
            raise BrokerError("INVALID_ARGUMENT", "Unknown or duplicate document field")
        self.require_fields(access.scope, args.fields)
        rows = self.eligible(access.scope)
        if args.version_policy != access.scope.document_version_policy:
            raise BrokerError(
                "SCOPE_DENIED",
                f"version_policy must be '{access.scope.document_version_policy}' for this task; "
                "use the scope's policy unchanged across pages. 'pinned' includes all versions "
                "in the pinned release, not only the latest family version.",
            )
        for field in ("document_types", "departments", "service_ids", "document_ids"):
            requested = getattr(args, field)
            if requested is not None:
                key = {
                    "document_types": "document_type",
                    "departments": "department",
                    "document_ids": "document_id",
                    "service_ids": "service_ids",
                }[field]
                rows = [
                    r
                    for r in rows
                    if (
                        set(requested).intersection(r[key])
                        if field == "service_ids"
                        else r[key] in requested
                    )
                ]
        unknown_effective = 0
        if args.effective_at:
            at = instant(args.effective_at)
            unknown_effective = sum(not r.get("effective_from") for r in rows)
            rows = [
                r
                for r in rows
                if r.get("effective_from")
                and instant(r["effective_from"]) <= at
                and (not r.get("effective_to") or at < instant(r["effective_to"]))
            ]
        request = args.model_dump(exclude={"cursor"})
        offset = await self.records.offset(access, "enumerate_documents", request, args.cursor)
        coverage = {
            "method": "enumeration",
            "total_count": len(rows),
            "count_unit": "document versions",
            "population_hash": self.population_hash(rows),
            "semantic_inspection": False,
            "pinned_versions": access.scope.pinned_versions,
            "excluded_unknown_effective_start": unknown_effective,
            "population_definition": request,
        }
        page = []
        for row in rows[offset : offset + args.limit]:
            item = {f: row.get(f) for f in args.fields}
            # Registered handles expose neither source paths nor private authoring metadata.
            item["document_ref"] = (
                "DOC-"
                + digest(
                    serialized(
                        [
                            str(access.context.lease.task_id),
                            self.store.build_id,
                            row["document_id"],
                            row["source_sha256"],
                        ]
                    )
                )[:40]
            )
            if len(serialized(page + [item]).encode()) > MAX_PAGE_BYTES - 4096:
                if not page:
                    raise BrokerError("RESULT_TOO_LARGE", "Document metadata exceeds page bound")
                break
            scope = access.scope.model_copy(update={"document_ids": [row["document_id"]]})
            await self.records.put(
                access,
                "document",
                {
                    "document_id": row["document_id"],
                    "version": str(row["version"]),
                    "release": self.store.build_id,
                    "source_sha256": row["source_sha256"],
                },
                coverage,
                ref=item["document_ref"],
                scope=scope,
            )
            page.append(item)
        end = offset + len(page)
        more = end < len(rows)
        cursor = (
            await self.records.cursor(access, "enumerate_documents", request, end) if more else None
        )
        return {
            "schema_version": 1,
            "items": page,
            "truncated": more,
            "next_cursor": cursor,
            "coverage": {**coverage, "returned_count": len(page), "enumerated_through": end},
        }

    async def spans(self, access, args):
        self.require_observation_fields(access.scope)
        entry = await self.records.get(access, args.document_ref, kinds=["document"])
        doc = entry["payload"]
        allowed = {r["document_id"]: r for r in self.eligible(access.scope)}
        row = allowed.get(doc["document_id"])
        if (
            not row
            or str(row["version"]) != doc["version"]
            or row["source_sha256"] != doc["source_sha256"]
        ):
            raise BrokerError("SOURCE_VERSION", "Document identity no longer matches its reference")
        source = self.store.sources[row["document_id"]]
        lower, upper = 0, len(source)
        section = row
        if args.section_id:
            if args.section_id not in row["section_ids"]:
                raise BrokerError("INVALID_ARGUMENT", "Section does not belong to this document")
            section = self.store.sections[args.section_id]
            lower, upper = section["char_start"], section["char_end"]
        start = max(lower, args.char_start)
        stop = upper if args.char_end is None else args.char_end
        if not lower <= start < stop <= upper:
            raise BrokerError("INVALID_ARGUMENT", "Invalid exact character range")
        request = args.model_dump(exclude={"cursor"})
        offset = await self.records.offset(access, "read_spans", request, args.cursor)
        a, b = start + offset, min(start + offset + args.max_chars, stop)
        if a >= stop:
            raise BrokerError("INVALID_CURSOR", "Cursor is beyond the requested span")
        item = observation(
            self.store.ref(section, a, b),
            row["title"],
            source[a:b],
            is_partial=a > 0 or b < len(source),
            remaining_spans=[(x, y) for x, y in ((0, a), (b, len(source))) if x < y],
            effective_from=row.get("effective_from"),
            effective_to=row.get("effective_to"),
        )
        more = b < stop
        cursor = (
            await self.records.cursor(access, "read_spans", request, b - start) if more else None
        )
        return {
            "schema_version": 1,
            "observations": [item.model_dump(mode="json")],
            "truncated": more,
            "next_cursor": cursor,
            "coverage": {
                "method": "targeted",
                "document_id": row["document_id"],
                "version": doc["version"],
                "requested_range": [start, stop],
                "returned_range": [a, b],
                "remaining_requested_chars": stop - b,
                "semantic_inspection": False,
            },
        }
