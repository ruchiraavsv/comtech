# Local file logging and Phoenix integration plan

Status: implemented and verified locally on 2026-09-27. See
[usage and storage](../local-observability.md) and [validation](../validation.md).

This extends the implemented [development infrastructure plan](development-infrastructure.md). Local development gains persistent operational logs and searchable execution traces without external credentials. Hosted LangSmith remains available for the assignment demonstration.

## Decisions and scope

- Persist backend operational logs as newline-delimited JSON files, retaining console output.
- Run Phoenix as an optional local Compose service, with SQLite on a named volume. Its browser UI provides trace exploration and filtering.
- Instrument LangGraph with the documented OpenInference LangChain instrumentor and export directly to Phoenix using OpenTelemetry over HTTP. Phoenix already includes a trace collector; a separate OpenTelemetry Collector is unnecessary for this milestone.
- Use the existing single mock node to validate success, failure, concurrent runs, interruption, and replay behavior. No real model or vector calls are needed.
- Keep PostgreSQL as the source of checkpoints and application event replay. Phoenix stores diagnostic traces, not resumable application state.
- Preserve hosted LangSmith as a separate opt-in integration. Do not route LangSmith SDK exports into Phoenix in this milestone; use Phoenix's documented instrumentation to get the expected AI-specific attributes.
- Implement local and hosted modes individually first. Simultaneous export to both destinations is deferred until needed and tested.

Here, "local files" means application JSON logs plus Phoenix's SQLite database files. A second archive of raw OTLP trace JSON is not included. If raw trace files become a requirement, add an OpenTelemetry Collector with file export and Phoenix export later; do not build a custom trace serialization format now.

## Data paths

```text
FastAPI / LangGraph
  |-- structured operational logs --> console + rotating JSONL files
  |-- OpenInference spans ---------> Phoenix OTLP HTTP endpoint
  |                                   |-- SQLite in persistent volume
  |                                   `-- browser UI at localhost:6006
  `-- checkpoints / run events ----> existing PostgreSQL volume

Hosted demo: native LangSmith tracing instead of local Phoenix instrumentation
```

The initial file sink covers backend application logs. Explicitly document which Uvicorn loggers also flow through it. Streamlit and database/container logs remain available through Compose logs; collecting every service's logs is a later addition. Phoenix is not a general JSON-log search UI: use PowerShell/rg for file searches. Grafana/Loki and a standalone metrics database are outside this milestone.

## 1. Explicit configuration

Add application-owned configuration, documenting that these names are our settings rather than framework environment variables:

| Setting | Proposed behavior |
| --- | --- |
| `OBSERVABILITY_MODE` | `off`, `phoenix`, or `langsmith` |
| `PHOENIX_PROJECT_NAME` | `comtech-local` |
| `PHOENIX_TRACE_ENDPOINT` | Compose: `http://phoenix:6006/v1/traces`; host Python: `http://localhost:6006/v1/traces` |
| `LOG_FILE_ENABLED` | Enabled in the local observability setup; independent of tracing mode |
| `LOG_DIRECTORY` | Container: `/app/logs`; host Python: ignored `./var/logs` |
| `LOG_MAX_BYTES` | 10 MiB per file initially |
| `LOG_BACKUP_COUNT` | 5 backups plus the active file |

Resolve mode centrally. For compatibility, when `OBSERVABILITY_MODE` is absent, retain the existing `LANGSMITH_TRACING` behavior. When an explicit mode is provided, validate conflicting settings rather than silently exporting to an unintended destination. Require the LangSmith key only for hosted mode. Phoenix mode must work with no provider keys and with hosted LangSmith tracing disabled.

Ordinary tests default to tracing off. Local tracing dependencies must be present when Phoenix mode is selected; a missing dependency produces a clear startup configuration error, never a fallback to cloud tracing. Exclude local services and paths from the existing remote Compose configuration by default.

## 2. Persistent application logs

Extend `src/comtech/logging.py` and add lifecycle management where needed:

- Keep one JSON object per line with UTC timestamp, severity, event name, logger, and allowlisted correlation fields. Add a schema version, service name and environment.
- Use standard-library queue-based logging so file writes and rotation run outside the async request path. Define a bounded queue and an explicit overflow policy: discard excess diagnostic records with a rate-limited visible warning, rather than blocking the graph or growing memory indefinitely.
- Use a rotating file handler owned by a single listener/writer. Preserve the existing one-worker constraint; do not allow several workers to rotate the same file.
- Initialize and tear down idempotently during reload, drain queued records on graceful shutdown within a bounded timeout, and avoid duplicate console/file handlers.
- Persist under an ignored `var/logs` host bind mount for easy inspection on this Windows machine. Verify the non-root container can write through Podman. If that mount is incompatible, use a named volume and provide an explicit export command.
- Enforce size-based retention. Ordinary stop/start and container recreation must not truncate existing files. Abrupt process/host failure may lose queued records; these logs are not a transactional audit trail.
- Preserve allowlisting: no credentials, authorization headers, full request bodies, or raw exception payloads in operational logs. Synthetic graph input/output belongs in traces.
- Validate the file destination at startup when file logging is enabled. Report runtime write failures to console without failing otherwise successful runs.

Document a command to search all active/rotated files by run ID and a PowerShell JSON example for filtering severity. Keep generated data out of Git and image build contexts.

## 3. Phoenix service and storage

- Add an optional local observability Compose overlay and a small wrapper entry point using the existing Podman/Docker selection behavior. The wrapper must select base + development + observability files consistently for up, down, logs and config.
- Pin a tested Phoenix image version/digest during implementation. Configure `PHOENIX_WORKING_DIR` to a writable named-volume mount so SQLite survives container recreation.
- Bind only the UI/HTTP port to `127.0.0.1:6006`; keep export traffic on the Compose network. No public exposure or LangSmith key is needed.
- Add a health check supported by the selected image. Verify volume ownership and startup with the actual Podman provider; do not assume the image contains curl or wget.
- Provide status, restart, storage inspection, backup and explicit reset instructions. Back up SQLite using a supported consistent method, or stop Phoenix before copying its database files. Never delete volumes as part of normal startup.
- Establish a documented local trace retention policy using the pinned Phoenix version's supported settings if available. Otherwise document manual project cleanup and storage monitoring rather than claiming automatic retention.

## 4. Instrumentation and correlation

- Add a small `src/comtech/observability.py` module responsible for provider initialization, instrumenting once, flush and shutdown.
- Lock compatible OpenInference LangChain instrumentation, OTel SDK/OTLP HTTP exporter and Phoenix helper dependencies as needed. Keep the Phoenix server in its container, not in the backend Python environment.
- Set up instrumentation before graph execution, using an explicitly owned tracer provider and batch export. Validate async context propagation with simultaneous conversations.
- Give each execution an application root span covering actual streamed graph execution. Start it inside the streaming generator, not just while constructing the HTTP response; end it on completion, failure or cancellation. Let instrumented graph/node spans nest beneath it.
- Attach application `run_id`, `thread_id`, `request_id`, environment and code revision. Use OpenInference's supported session metadata to group executions from one conversation.
- Preserve the existing application IDs and database/API contract. The current `trace_id` is assigned by the application for LangSmith correlation; do not assume it equals OTel's generated trace ID. Add distinct `otel_trace_id` and `otel_span_id` fields to logs and expose/persist the mapping with the run where appropriate. Use an additive migration if the mapping needs database storage.
- Capture only synthetic mock inputs/outputs initially. Define configurable input/output masking before using real data. Do not add overlapping instrumentors that duplicate the same graph or model spans.
- Bound exporter timeouts and queue size. Phoenix outages produce diagnostic warnings and must not fail API readiness, delay streaming indefinitely or prevent graph completion. Flush on graceful shutdown outside the event loop with a bounded wait. In-memory export queues do not guarantee delivery during a crash or prolonged outage.
- Saved-event playback must not create new graph-execution spans. Checkpoint resume is a new execution with an explicit link to the prior application run.

## 5. Implementation order and acceptance

1. Add settings, queued file logging, retention and focused tests. Verify valid JSON, correlation, rotation, restart append behavior and safe failure handling.
2. Add Phoenix Compose overlay, persistent volume and wrapper/docs. Validate merged configuration and start it using Podman.
3. Add instrumentation and lock dependencies. Run the actual mock graph and inspect the Phoenix UI for a parent execution, nested node, inputs/outputs, timings and status.
4. Verify two simultaneous conversations do not share context; two executions of one conversation can be found together. Find a run in Phoenix and locate its corresponding log records using saved correlation fields.
5. Exercise a deliberate failure and an interrupted stream. Verify span status/end timing and that application terminal events/checkpoints retain their existing semantics.
6. Restart/recreate API and Phoenix without removing storage. Confirm old logs and traces remain searchable. Exercise file rotation with small test limits and verify the documented backup/restore procedure on isolated data.
7. Stop Phoenix and run the mock graph: SSE still completes, readiness remains healthy, and exporter failures are visible. Restart Phoenix and confirm subsequent traces arrive; do not assert guaranteed recovery of already dropped spans.
8. Inspect effective configuration/export destinations: local mode has no hosted LangSmith exporter and requires no external keys. Verify replay adds no graph run and test shutdown/reload for duplicate instrumentation.
9. Run existing meaningful streaming, replay and checkpoint tests; build affected runtime images and validate normal development/remote Compose configurations. Update README, deployment guidance and validation evidence.

Implementation is recorded as a coherent infrastructure milestone. Unrelated user files are excluded from the change.

## Documentation and expected files

- Modify settings, logging and FastAPI lifecycle/run integration; add observability module.
- Modify `pyproject.toml` and lockfile, environment examples, ignore files and any additive run-metadata migration.
- Add local observability Compose overlay and wrapper, focused tests, and an opt-in local trace smoke check.
- Update README and deployment/validation documents with exact verified commands, storage locations, UI access, troubleshooting, retention and loss guarantees.
- Keep hosted LangSmith verification credential-dependent and separate. No OpenAI/Pinecone keys are needed for this milestone.

## References

- [Phoenix LangGraph instrumentation](https://arize.com/docs/phoenix/integrations/python/langgraph/langgraph-tracing): LangGraph uses the OpenInference LangChain instrumentor.
- [Phoenix Docker and persistent SQLite deployment](https://arize.com/docs/phoenix/self-hosting/deployment-options/docker): container service, HTTP ingestion and persistent working directory.
- [Phoenix configuration](https://arize.com/docs/phoenix/self-hosting/configuration): verify exact server options against the pinned release.
- [OpenTelemetry Collector file exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/fileexporter): possible later raw OTLP archive; currently alpha and not part of this milestone.
