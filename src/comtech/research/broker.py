"""Document data plane. Management methods/capabilities never enter the model tool schema."""

import asyncio
import json
from copy import deepcopy

from pydantic import ValidationError

from comtech.agents.budget import digest, serialized
from comtech.agents.contracts import ReadDocumentSectionsResult, ToolFailure, ToolResult
from comtech.retrieval.store import DocumentArgumentError, ReadArgs, SearchArgs
from comtech.retrieval.tools import DOCUMENT_SCHEMAS, DocumentTools, document_schemas

from .accounting import bind, source_call
from .artifacts import Artifacts, json_bytes
from .broker_contracts import (
    MAX_PAGE_BYTES,
    BrokerError,
    DescribeArgs,
    DocumentSetSpec,
    ReadArtifactArgs,
    SpanRequest,
    WriteArtifactArgs,
)
from .documents import Documents
from .ledger import AccountingError
from .records import Records

REQUESTS = {
    "describe": DescribeArgs,
    "knowledge_search": SearchArgs,
    "read_document_sections": ReadArgs,
    "enumerate_documents": DocumentSetSpec,
    "read_spans": SpanRequest,
    "read_artifact": ReadArtifactArgs,
    "write_artifact": WriteArtifactArgs,
}


class Broker:
    def __init__(self, capabilities, store, search, counter, limits, artifact_root):
        self.capabilities = capabilities
        self.records = Records(capabilities)
        self.documents = Documents(store, self.records)
        self.tools = DocumentTools(store, search, counter, limits)
        self.artifacts = Artifacts(artifact_root, self.records)
        self.counter, self.limits = counter, limits

    async def call(self, token, operation, arguments, *, request_id):
        access = await self.capabilities.resolve(token, operation)
        eligible = self.documents.eligible(access.scope)  # Recheck source pins on every path.
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 200:
            raise BrokerError("INVALID_ARGUMENT", "Invalid request identity")
        raw = json_bytes(arguments)
        if len(raw) > MAX_PAGE_BYTES and operation != "write_artifact":
            raise BrokerError("INVALID_ARGUMENT", "Data request exceeds bound")
        try:
            args = (
                ReadArgs.for_limits(arguments, self.limits)
                if operation == "read_document_sections"
                else REQUESTS[operation].model_validate(arguments)
            )
        except ValidationError:
            raise BrokerError("INVALID_ARGUMENT", "Invalid data request schema") from None
        request_hash = digest(serialized([operation, args.model_dump(mode="json")]))
        binding = str(access.execution_id) if access.execution_id else "direct"
        lease = access.context.lease
        async with self.capabilities.pool.connection() as conn, conn.transaction():
            await access.context.ledger._active(conn, lease, "exploration")
            prior = await (
                await conn.execute(
                    "SELECT request_hash FROM research_data_requests WHERE task_id=%s "
                    "AND binding=%s AND request_id=%s",
                    (lease.task_id, binding, request_id),
                )
            ).fetchone()
            if prior and prior["request_hash"] != request_hash:
                raise BrokerError("INVALID_ARGUMENT", "Request identity is immutable")
            if not prior:
                await conn.execute(
                    "INSERT INTO research_data_requests VALUES(%s,%s,%s,%s)",
                    (lease.task_id, binding, request_id, request_hash),
                )
        maximum_rows = args.limit if hasattr(args, "limit") else 100
        if operation == "enumerate_documents":
            # The pinned local manifest bounds delivery even when a caller requests a
            # larger page. Reserving 1000 discoveries for a 132-document release would
            # incorrectly exhaust the 500-document objective allowance before any read.
            maximum_rows = min(maximum_rows, len(eligible))
        requested = {
            "data_requests": 1,
            "control_steps": 1,
            "bytes": MAX_PAGE_BYTES,
            "rows": maximum_rows,
        }
        if operation in ("knowledge_search", "enumerate_documents"):
            requested["documents_discovered"] = (
                maximum_rows if operation == "enumerate_documents" else 12
            )
        if operation in ("read_document_sections", "read_spans"):
            requested["documents_opened"] = 1

        async def execute():
            try:
                async with asyncio.timeout(self.limits.tool_timeout_seconds):
                    await self.capabilities.resolve(token, operation)
                    value = await self.execute(access, operation, args)
                    await self.capabilities.resolve(token, operation)
                    if len(serialized(value).encode()) > MAX_PAGE_BYTES - 2048:
                        raise BrokerError("RESULT_TOO_LARGE", "Data result exceeds byte bound")
                    registered, coverage, docs = await self.register(access, operation, value)
                    coverage = {
                        **coverage,
                        "operation": operation,
                        "request": args.model_dump(mode="json", exclude={"value"}),
                        "requested_scope_ref": access.scope.scope_ref,
                    }
                    inputs = list(coverage.get("inspected_refs", []))
                    if operation == "enumerate_documents":
                        inputs.extend(item["document_ref"] for item in registered["items"])
                    elif operation in ("read_artifact", "write_artifact"):
                        inputs.append(registered["artifact_ref"])
                    receipt = await self.records.put(
                        access, "page", registered, coverage, inputs=inputs
                    )
                    reply = {
                        "value": registered,
                        "receipt_ref": receipt,
                        "coverage": coverage,
                        "documents": docs,
                    }
                    if len(serialized(reply).encode()) > MAX_PAGE_BYTES:
                        raise BrokerError(
                            "RESULT_TOO_LARGE", "Registered result exceeds byte bound"
                        )
                    return reply
            except (BrokerError, DocumentArgumentError) as error:
                return {
                    "value": {
                        "error": {
                            "tool_name": operation,
                            "code": getattr(error, "code", "INVALID_ARGUMENT"),
                            "message": str(error),
                        }
                    },
                    "receipt_ref": None,
                    "coverage": {},
                    "documents": [],
                }
            except (ValueError, KeyError):
                return {
                    "value": {
                        "error": {
                            "tool_name": operation,
                            "code": "INVALID_ARGUMENT",
                            "message": "Arguments or source contract invalid.",
                        }
                    },
                    "receipt_ref": None,
                    "coverage": {},
                    "documents": [],
                }
            except TimeoutError:
                return {
                    "value": {
                        "error": {
                            "tool_name": operation,
                            "code": "TIMEOUT",
                            "message": "Data operation deadline expired.",
                        }
                    },
                    "receipt_ref": None,
                    "coverage": {},
                    "documents": [],
                }
            except AccountingError:
                raise
            except Exception:
                return {
                    "value": {
                        "error": {
                            "tool_name": operation,
                            "code": "UNAVAILABLE",
                            "message": "Source unavailable; no replacement facts.",
                        }
                    },
                    "receipt_ref": None,
                    "coverage": {},
                    "documents": [],
                }

        def measure(reply):
            value = reply["value"]
            actual = {
                **requested,
                "bytes": len(serialized(reply).encode()),
                "rows": len(value.get("observations", value.get("items", []))),
            }
            documents = {}
            for metric in ("documents_discovered", "documents_opened"):
                if metric in requested:
                    documents[metric] = set(reply["documents"])
                    actual[metric] = len(documents[metric])
            return actual, documents

        with bind(access.context):
            reply = await access.context.call(
                "data",
                requested,
                execute,
                measure,
                replay_key="broker:" + digest(serialized([binding, request_id, request_hash])),
                encode=lambda value: value,
                decode=lambda value: value,
            )
        await self.capabilities.resolve(token, operation)
        return reply

    async def execute(self, access, operation, args):
        if operation in DOCUMENT_SCHEMAS:
            self.documents.require_observation_fields(access.scope)
            allowed = {r["document_id"] for r in self.documents.eligible(access.scope)}
            result = await self.tools.call(operation, args.model_dump(), allowed_ids=allowed)
            maximum = (
                self.limits.max_tokens_per_read if operation == "read_document_sections" else 3000
            )
            if self.counter.count(result) > maximum:
                raise BrokerError("RESULT_TOO_LARGE", "Document result exceeded token bound")
            if any(o.source_ref.source_id not in allowed for o in result.observations):
                raise BrokerError("SCOPE_DENIED", "Source returned an out-of-scope document")
            return result.model_dump(mode="json")
        if operation == "describe":
            return self.documents.description(access, args)
        if operation == "enumerate_documents":
            return await source_call(lambda: self.documents.enumerate(access, args))
        if operation == "read_spans":
            return await source_call(lambda: self.documents.spans(access, args))
        if operation == "write_artifact":
            return await self.artifacts.write(access, args)
        if operation == "read_artifact":
            return await self.artifacts.read(access, args)
        raise BrokerError("CAPABILITY_UNAVAILABLE", "Unavailable data operation")

    async def register(self, access, operation, value):
        value = deepcopy(value)
        coverage = value.get(
            "coverage",
            {
                "method": "sample" if operation == "knowledge_search" else "targeted",
                "population_complete": False,
                "pinned_versions": access.scope.pinned_versions,
            },
        )
        if operation == "describe":
            coverage = {
                "method": "aggregate",
                "aggregate": "count",
                "count_unit": value["count_unit"],
                "total_count": value["total_count"],
                "population_hash": value["population_hash"],
                "population_complete": True,
                "semantic_inspection": False,
                "pinned_versions": access.scope.pinned_versions,
            }
        refs, documents = [], set()
        for item in value.get("observations", []):
            source = item["source_ref"]
            document = self.tools.store.documents.get(source["source_id"])
            text = self.tools.store.sources.get(source["source_id"], "")
            start, end = source.get("char_start"), source.get("char_end")
            if (
                not document
                or source["source_type"] != "document"
                or str(document["version"]) != source["version"]
                or not isinstance(start, int)
                or not isinstance(end, int)
                or not 0 <= start < end <= len(text)
                or text[start:end] != item["content"]
                or digest(item["content"]) != item["content_hash"]
                or (
                    source.get("section_id") and source["section_id"] not in document["section_ids"]
                )
            ):
                raise BrokerError("SOURCE_VERSION", "Observation does not match the pinned source")
            original = item["observation_id"]
            ref = "OBS-" + digest(serialized([str(access.context.lease.task_id), original]))[:40]
            item["observation_id"] = ref
            if operation == "knowledge_search" and value.get("details"):
                try:
                    details = json.loads(value["details"])
                except ValueError:
                    details = {}
                for ranking in details.get("rankings", []):
                    if ranking.get("observation_id") == original:
                        ranking["observation_id"] = ref
                if details:
                    value["details"] = serialized(details)
            # Observation identity excludes retrieval time; first durable observation wins.
            item["retrieved_at"] = await self.first_observed(ref, item["retrieved_at"])
        if operation in DOCUMENT_SCHEMAS:
            self.bound_document_result(operation, value)
        for item in value.get("observations", []):
            source, ref = item["source_ref"], item["observation_id"]
            scope = access.scope.model_copy(update={"document_ids": [source["source_id"]]})
            await self.records.put(access, "observation", item, coverage, ref=ref, scope=scope)
            refs.append(ref)
            documents.add(serialized([source["source_id"], source["version"]]))
        for item in value.get("items", []) if operation == "enumerate_documents" else []:
            if "document_ref" in item:
                record = await self.records.get(access, item["document_ref"], kinds=["document"])
                doc = record["payload"]
                documents.add(serialized([doc["document_id"], doc["version"]]))
        coverage = {**coverage, "inspected_refs": refs}
        return value, coverage, sorted(documents)

    def bound_document_result(self, operation, value):
        """Durable IDs are part of the returned context, including updated rankings/counts."""
        is_read = operation == "read_document_sections"
        maximum = self.limits.max_tokens_per_read if is_read else 3000
        while True:
            if is_read:
                for _ in range(4):
                    value["token_count"] = self.counter.count(value)
            if self.counter.count(value) <= maximum:
                return
            if not value["observations"]:
                raise BrokerError("RESULT_TOO_LARGE", "Document metadata exceeds token bound")
            value["observations"].pop()
            if is_read:
                value["omitted_sections"] = True
            else:
                details = json.loads(value["details"])
                remaining = {o["observation_id"] for o in value["observations"]}
                details["rankings"] = [
                    r for r in details.get("rankings", []) if r["observation_id"] in remaining
                ]
                value["details"] = serialized(details)

    async def first_observed(self, ref, fallback):
        async with self.capabilities.pool.connection() as conn:
            old = await (
                await conn.execute(
                    "SELECT payload->>'retrieved_at' AS time "
                    "FROM research_data_records WHERE ref=%s",
                    (ref,),
                )
            ).fetchone()
        return old["time"] if old else fallback


class ResearchDocumentTools:
    """Agent-facing document tools; capability/receipt metadata stays in trusted orchestration."""

    def __init__(self, broker, token):
        self.broker, self.token = broker, token

    @property
    def schemas(self):
        return document_schemas(self.broker.limits)

    async def call(self, name, arguments, *, request_id):
        if name not in DOCUMENT_SCHEMAS:
            return ToolResult(
                error=ToolFailure(
                    tool_name=name,
                    code="CAPABILITY_UNAVAILABLE",
                    message="Research document tool is unavailable.",
                )
            )
        try:
            reply = await self.broker.call(self.token, name, arguments, request_id=request_id)
        except BrokerError as error:
            return ToolResult(
                error=ToolFailure(tool_name=name, code=error.code, message=str(error))
            )
        value = reply["value"]
        kind = (
            ReadDocumentSectionsResult
            if name == "read_document_sections" and not value.get("error")
            else ToolResult
        )
        return kind.model_validate(value)
