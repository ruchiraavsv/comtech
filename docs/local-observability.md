# Local logs and Phoenix

The mock graph needs no provider keys. Phoenix 20.16.0 is pinned by image digest;
OpenInference and OTel dependencies are pinned in `uv.lock`.

## Start and inspect

After the normal `.env`/Podman setup:

```powershell
./scripts/observability.cmd up --build -d
./scripts/observability.cmd ps
./scripts/observability.cmd logs -f api phoenix
```

This wrapper selects `compose.yaml`, `compose.dev.yaml` and
`compose.observability.yaml`. Use it for subsequent stack commands. Docker users
can set `$env:CONTAINER_ENGINE='docker'`; no Docker Desktop is needed on this PC.

- Application: http://localhost:8501
- Phoenix: http://localhost:6006 — open `comtech-local`.
- API readiness: http://localhost:8000/health/ready — reports mode `phoenix`.

Send a message, then `/fail`. In Phoenix's Spans view, open
`conversation_execution`, expand `mock_conversation`, and select `mock_node`.
Inspect timings, inputs, outputs and errors. Root rows show the latest input and
up to 16,000 characters of the streamed answer; nested spans hold framework data.
The mock has no LLM calls, so token/cost values are zero or absent.

Each application thread becomes a Phoenix session. Metadata contains `run_id`,
`request_id`, `thread_id` and the application trace UUID. Use the span filter, for
example `metadata["run_id"] == "<run-uuid>"`, or search using the OTel trace ID.
`GET /api/runs/{id}` returns `otel_trace_id` after execution starts. This 32-digit
hex ID differs from the existing UUID `trace_id` / `X-Trace-ID`, which remains the
LangSmith correlation ID. Both appear in logs.

Phoenix visualizes execution traces; it does not index the JSON application logs.
Checkpoints and recorded SSE events still live in PostgreSQL. Saved-event replay
creates no graph trace; explicit resume creates a new run/trace linked by
`parent_run_id` metadata.

## File logs and search

Backend JSONL files are in `var/logs/api.jsonl` and numbered rotations on the host.
The API writes there as its non-root user through a bind mount, verified on Podman.
The directory is excluded from Git and container build contexts.

```powershell
Get-Content var/logs/api.jsonl -Tail 20 -Wait
Get-ChildItem var/logs/api.jsonl* | Select-String -SimpleMatch '<run-uuid>'
# With ripgrep installed:
rg '<run-uuid>' var/logs
# Parse JSON and filter errors:
Get-ChildItem var/logs/api.jsonl* | Get-Content |
    ConvertFrom-Json | Where-Object severity -EQ ERROR
```

Defaults: 10 MiB per file, five backups plus the active file (approximately
60 MiB maximum, excluding a single unusually large record). Rotation is based on
size, not days. Files append across restart/recreation. Settings:
`LOG_FILE_ENABLED`, `LOG_DIRECTORY`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`.

One queue listener owns file rotation. The bounded queue holds 2,048 records;
overflow drops records with a rate-limited console warning. Graceful shutdown
allows three seconds to drain it. Abrupt crashes can lose buffered records.
This is operational logging, not an audit ledger.

Application events use an allowlist of correlation fields. Arbitrary SDK/Uvicorn
messages become `library_log`, preserving severity/logger and exception type but
excluding potentially sensitive URLs or error payloads. Uvicorn logs emitted
during the application lifespan join the file sink; its reloader/startup messages
outside that lifespan remain console-only. Streamlit, Phoenix and Postgres logs
remain in `compose logs`; this milestone does not aggregate every service's logs.

## Storage, retention and backup

Phoenix uses SQLite under `/data`, backed by the `comtech_phoenix-data` named
volume in the Podman VM. This is separate from the host log directory and the
Postgres volume. Phoenix is bound only to host loopback and has authentication
disabled for local development.

The configured default Phoenix trace retention threshold is seven days, with the
pinned server's weekly cleanup schedule; expiry is not immediate at day seven. Check project
Config if changing retention for an existing project; explicit project policies
can override the default. Trace expiry does not necessarily shrink SQLite's
allocated file size. Use `podman system df` to monitor local storage.

```powershell
./scripts/observability.cmd down
./scripts/observability.cmd up -d
```

These commands retain history. Do not add `--volumes` unless intentionally
deleting this stack's Postgres and Phoenix history. Host `var/logs` files remain
even after named-volume deletion.

Use SQLite's online backup API rather than copying a live database while its WAL
is changing. This writes a backup inside the volume, then copies it to the host:

```powershell
podman exec comtech-phoenix-1 python -c "import sqlite3; source=sqlite3.connect('/data/phoenix.db'); backup=sqlite3.connect('/data/phoenix-backup.db'); source.backup(backup); print(backup.execute('PRAGMA integrity_check').fetchone()); backup.close(); source.close()"
podman cp comtech-phoenix-1:/data/phoenix-backup.db var/phoenix-backup.db
```

For restoration, stop Phoenix and restore into a **new empty volume or directory**
with the backup named `phoenix.db`. Start the same pinned image against that
directory using `PHOENIX_WORKING_DIR=/data`; verify historical projects/traces
before switching the normal service to it. Do not combine the restored file with
old `phoenix.db-wal` or `phoenix.db-shm` files. A restore into an isolated container
is covered by the recorded validation. Backups themselves need manual retention.

## Configuration and failure behavior

`OBSERVABILITY_MODE` is an application setting: `off`, `phoenix`, or `langsmith`.
Without it, the previous `LANGSMITH_TRACING` setting still selects hosted tracing
or off. Explicit local/off modes reject `LANGSMITH_TRACING=true`. The local overlay
sets Phoenix mode and hosted tracing false; it does not modify your `.env` keys.

Phoenix receives OpenInference spans directly over HTTP at
`http://phoenix:6006/v1/traces`. Host Python instead uses
`http://localhost:6006/v1/traces`. `PHOENIX_PROJECT_NAME` selects the project.
There is no separate OTel Collector, raw trace-file archive, or metrics store.
Phoenix can calculate summaries from captured spans.

Local tracing does not initialize a LangSmith client. To switch back to the
hosted demo, use the normal Compose stack with `OBSERVABILITY_MODE=langsmith`
and a LangSmith key. File logging is independent of tracing mode.

`TRACE_HIDE_INPUTS=true` and `TRACE_HIDE_OUTPUTS=true` mask the corresponding
captured span fields. Only synthetic data is used now. These flags do not scrub
arbitrary metadata or error text, and do not change application state persistence.

Exports run in bounded background batches (2,048 spans, batches of 128, two-second
HTTP timeout). Phoenix outages log `trace_export_failed`; the graph still runs
and readiness checks only required application storage. Graceful tracing shutdown
has a five-second application-level limit. Queue overflow, prolonged outages and
process crashes may lose traces; there is no durable delivery guarantee or cloud
fallback. After recovery, new traces are exported normally.

If startup fails to open the log directory, check its host permissions. If traces
are absent, check the mode, Phoenix health, project name and export warnings.
Rebuild after changing dependencies. Use one API worker; multi-process file
rotation and global instrumentation coordination are not supported.

## Validation commands

```powershell
py -m uv run python scripts/verify_observability.py
./scripts/observability.cmd up -d --force-recreate api phoenix
py -m uv run python scripts/verify_observability.py --verify-saved
./scripts/test.cmd -q
```

The smoke creates synthetic success/failure runs, checks session grouping,
nested spans, log correlation and replay. The saved check verifies those runs
after replacement. Tests cover isolated graph instrumentation and logging plus
HTTP streaming against an isolated Postgres database in off and Phoenix modes.

References: [Phoenix LangGraph instrumentation](https://arize.com/docs/phoenix/integrations/python/langgraph/langgraph-tracing),
[Phoenix container persistence](https://arize.com/docs/phoenix/self-hosting/deployment-options/docker).
