"""Immutable JSON/Parquet files outside source storage; no caller-controlled file paths."""

import asyncio
import hashlib
import json
import math
import os
import time
from pathlib import Path
from uuid import UUID, uuid4

from comtech.agents.budget import serialized

from .accounting import source_call
from .broker_contracts import MAX_ARTIFACT_BYTES, MAX_PAGE_BYTES, BrokerError


def json_bytes(value):
    def check(item, depth=0):
        if depth > 24:
            raise BrokerError("INVALID_ARGUMENT", "Artifact nesting exceeds limit")
        if isinstance(item, dict):
            if any(not isinstance(k, str) for k in item):
                raise BrokerError("INVALID_ARGUMENT", "Artifact keys must be strings")
            for val in item.values():
                check(val, depth + 1)
        elif isinstance(item, list):
            for val in item:
                check(val, depth + 1)
        elif item is not None and type(item) not in (str, bool, int, float):
            raise BrokerError("INVALID_ARGUMENT", "Artifact contains an unsupported type")
        elif isinstance(item, float) and not math.isfinite(item):
            raise BrokerError("INVALID_ARGUMENT", "Nonfinite values must be explicit nulls")

    check(value)
    raw = serialized(value).encode()
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise BrokerError("RESULT_TOO_LARGE", "Artifact exceeds 32 MiB")
    return raw


class Artifacts:
    def __init__(self, root, records):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.records = records

    def path(self, objective_id, name):
        if len(name) != 32 or any(c not in "0123456789abcdef" for c in name):
            raise BrokerError("INVALID_REFERENCE", "Invalid stored artifact key")
        target = self.root / str(objective_id) / name
        if (
            not target.resolve().is_relative_to(self.root)
            or target.parent.is_symlink()
            or target.is_symlink()
        ):
            raise BrokerError("INVALID_REFERENCE", "Artifact path escaped storage")
        return target

    def encode(self, args):
        raw = json_bytes(args.value)
        schema = None
        if args.format == "parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq

            fields = set(args.value[0]) if args.value else set()
            if len(fields) > 100 or any(set(row) != fields for row in args.value):
                raise BrokerError("INVALID_ARGUMENT", "Parquet rows require consistent columns")
            if any(isinstance(v, (dict, list)) for r in args.value for v in r.values()):
                raise BrokerError("INVALID_ARGUMENT", "Parquet supports scalar columns only")
            table = pa.Table.from_pylist(args.value)
            sink = pa.BufferOutputStream()
            pq.write_table(table, sink, compression="NONE")
            raw, schema = sink.getvalue().to_pybytes(), str(table.schema)
        if len(raw) > MAX_ARTIFACT_BYTES:
            raise BrokerError("RESULT_TOO_LARGE", "Encoded artifact exceeds 32 MiB")
        return raw, schema

    async def write(self, access, args):
        if access.execution_id is None:
            raise BrokerError(
                "CAPABILITY_UNAVAILABLE", "Artifact writes require a registered execution"
            )
        inputs = [await self.records.get(access, r) for r in dict.fromkeys(args.input_refs)]
        input_documents = [r["source_scope"].get("document_ids") for r in inputs]
        output_scope = access.scope.model_copy(
            update={
                "document_ids": sorted({d for ids in input_documents for d in ids})
                if all(ids is not None for ids in input_documents)
                else access.scope.document_ids,
            }
        )
        async with self.records.pool.connection() as conn:
            execution = await (
                await conn.execute(
                    "SELECT record FROM research_executions WHERE id=%s", (access.execution_id,)
                )
            ).fetchone()
        manifest = execution["record"]
        if not manifest.get("code_hash") or not manifest.get("environment_digest"):
            raise BrokerError("INVALID_REFERENCE", "Execution provenance is incomplete")
        raw, schema = await source_call(lambda: asyncio.to_thread(self.encode, args))
        key = uuid4().hex
        path = self.path(access.context.lease.objective_id, key)

        def save():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())

        await source_call(lambda: asyncio.to_thread(save))
        coverage = {
            "method": "calculation",
            "input_refs": args.input_refs,
            "input_coverage_refs": [r["ref"] for r in inputs],
            "population_complete": False,
            "note": "Exact calculation over registered inputs; no inferred population coverage.",
        }
        payload = {
            "key": key,
            "format": args.format,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "schema": schema,
            "code_hash": manifest["code_hash"],
            "environment_digest": manifest["environment_digest"],
            "method": args.method,
            "units": args.units,
            "assumptions": args.assumptions,
            "extraction_version": args.extraction_version,
            "analysis_provenance": manifest.get("analysis_provenance", {}),
            "analysis_process": args.analysis_process.model_dump(mode="json")
            if args.analysis_process is not None
            else None,
        }
        try:
            # Cumulative per-execution storage cap is serialized on the objective lock.
            async with self.records.pool.connection() as conn, conn.transaction():
                await access.context.ledger._active(conn, access.context.lease, "finalization")
                size = await (
                    await conn.execute(
                        "SELECT COALESCE(sum((payload->>'bytes')::bigint),0) AS size "
                        "FROM research_data_records WHERE kind='artifact' AND execution_id=%s",
                        (access.execution_id,),
                    )
                ).fetchone()
                if size["size"] + len(raw) > MAX_ARTIFACT_BYTES:
                    raise BrokerError("RESULT_TOO_LARGE", "Execution artifact allowance exhausted")
                # Use the same transaction for the cap and immutable registration.
                ref = "ART-" + uuid4().hex
                from psycopg.types.json import Jsonb

                from comtech.agents.budget import digest

                await conn.execute(
                    """INSERT INTO research_data_records
                    (ref,objective_id,task_id,execution_id,kind,payload,content_hash,source_scope,
                     coverage,input_refs) VALUES(%s,%s,%s,%s,'artifact',%s,%s,%s,%s,%s)""",
                    (
                        ref,
                        access.context.lease.objective_id,
                        access.context.lease.task_id,
                        access.execution_id,
                        Jsonb(payload),
                        digest(serialized(payload)),
                        Jsonb(output_scope.model_dump(mode="json")),
                        Jsonb(coverage),
                        Jsonb(args.input_refs),
                    ),
                )
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return {
            "schema_version": 1,
            "artifact_ref": ref,
            "format": args.format,
            "bytes": len(raw),
            "content_hash": payload["sha256"],
            "coverage": coverage,
        }

    def load(self, row):
        payload = row["payload"]
        path = self.path(row["objective_id"], payload["key"])
        if not path.exists():
            raise BrokerError("ARTIFACT_UNAVAILABLE", "Artifact file is missing")
        with path.open("rb") as stream:
            raw = stream.read(MAX_ARTIFACT_BYTES + 1)
        if len(raw) != payload["bytes"] or hashlib.sha256(raw).hexdigest() != payload["sha256"]:
            raise BrokerError("HASH_MISMATCH", "Artifact content hash mismatch")
        if payload["format"] == "json":
            return json.loads(raw)
        if payload["format"] == "parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pq.read_table(pa.BufferReader(raw))
            if str(table.schema) != payload["schema"] or table.nbytes > MAX_ARTIFACT_BYTES:
                raise BrokerError("HASH_MISMATCH", "Artifact schema or size mismatch")
            return table.to_pylist()
        raise BrokerError("INVALID_REFERENCE", "Unsupported stored artifact format")

    async def read(self, access, args):
        row = await self.records.get(access, args.artifact_ref, kinds=["artifact"])
        value = await source_call(lambda: asyncio.to_thread(self.load, row))
        request = args.model_dump(exclude={"cursor"})
        offset = await self.records.offset(access, "read_artifact", request, args.cursor)
        rows = value if isinstance(value, list) else [value]
        page = []
        for item in rows[offset : offset + args.limit]:
            if len(serialized(page + [item]).encode()) > MAX_PAGE_BYTES - 4096:
                if not page:
                    raise BrokerError("RESULT_TOO_LARGE", "Artifact row exceeds page bound")
                break
            page.append(item)
        end = offset + len(page)
        more = end < len(rows)
        cursor = await self.records.cursor(access, "read_artifact", request, end) if more else None
        return {
            "schema_version": 1,
            "items": page,
            "total_count": len(rows),
            "truncated": more,
            "next_cursor": cursor,
            "coverage": row["coverage"],
            "artifact_ref": args.artifact_ref,
            "content_hash": row["payload"]["sha256"],
        }

    async def retain(self, access, refs):
        """Trusted final selection; preserve the complete input closure for 30 days."""
        seen = set()

        async def visit(ref):
            if ref in seen:
                return
            seen.add(ref)
            row = await self.records.get(access, ref)
            for child in row["input_refs"]:
                await visit(child)

        for ref in refs:
            await visit(ref)
        async with self.records.pool.connection() as conn, conn.transaction():
            await access.context.ledger._active(conn, access.context.lease, "finalization")
            await conn.execute(
                "UPDATE research_data_records SET retained=true,expires_at=GREATEST(expires_at,"
                "clock_timestamp()+interval '30 days') WHERE ref=ANY(%s)",
                (list(seen),),
            )

    async def prune(self):
        """Maintenance operation, never exposed through the execution data SDK."""
        async with self.records.pool.connection() as conn:
            candidates = await (
                await conn.execute(
                    """SELECT d.* FROM research_data_records d JOIN research_objectives o
                ON o.id=d.objective_id JOIN app_runs r ON r.id=o.run_id
                WHERE d.expires_at<clock_timestamp()
                AND (NOT d.expired OR (d.kind='artifact' AND NOT d.file_deleted))
                AND r.status IN ('completed','failed','cancelled')"""
                )
            ).fetchall()
        for row in candidates:
            async with self.records.pool.connection() as conn, conn.transaction():
                objective = await self.records.capabilities.ledger._lock(conn, row["objective_id"])
                if objective["status"] not in ("completed", "failed", "cancelled"):
                    continue
                await conn.execute(
                    "UPDATE research_data_records SET expired=true WHERE ref=%s", (row["ref"],)
                )
            if row["kind"] == "artifact":
                path = self.path(row["objective_id"], row["payload"]["key"])
                await asyncio.to_thread(path.unlink, missing_ok=True)
                async with self.records.pool.connection() as conn:
                    await conn.execute(
                        "UPDATE research_data_records SET file_deleted=true WHERE ref=%s",
                        (row["ref"],),
                    )
        await self.prune_orphans()
        return len(candidates)

    async def prune_orphans(self):
        """Recover files left before DB commit; never remove files for an active objective."""
        async with self.records.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT objective_id,payload->>'key' AS key FROM research_data_records "
                    "WHERE kind='artifact'"
                )
            ).fetchall()
            active = await (
                await conn.execute(
                    "SELECT o.id FROM research_objectives o JOIN app_runs r ON r.id=o.run_id "
                    "WHERE r.status NOT IN ('completed','failed','cancelled')"
                )
            ).fetchall()
        registered = {(str(r["objective_id"]), r["key"]) for r in rows}
        active_ids = {str(r["id"]) for r in active}

        def remove():
            cutoff = time.time() - 7 * 86400
            for directory in self.root.iterdir():
                try:
                    objective_id = UUID(directory.name)
                except ValueError:
                    continue
                if directory.is_symlink() or not directory.is_dir() or directory.name in active_ids:
                    continue
                for file in directory.iterdir():
                    if (
                        (directory.name, file.name) in registered
                        or file.is_symlink()
                        or not file.is_file()
                    ):
                        continue
                    try:
                        target = self.path(objective_id, file.name)
                    except BrokerError:
                        continue
                    if target.stat().st_mtime < cutoff:
                        target.unlink()

        await asyncio.to_thread(remove)
