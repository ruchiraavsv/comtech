# Infrastructure validation

Verified locally on 2026-09-27 with Podman 5.8.2, the existing WSL machine,
Compose provider 5.1.4, and locked Python 3.12 dependencies.

## Passed

- Windows preflight and `.cmd`/PowerShell argument-forwarding wrapper.
- API/UI container builds and development startup; migration service completes;
  Postgres, API readiness, and Streamlit health checks succeed.
- Six automated tests on Windows and six in Linux containers with isolated
  PostgreSQL 16.10. These cover incremental streaming before completion, same-thread
  conflict handling, independent conversations, session memory, durable history,
  cursor replay without execution, deliberate failure, timeout, disconnect,
  checkpoint resume, and rejection of accidental hosted targets in local tests.
- `scripts/verify_restart.py`: killed the API mid-node, restarted Postgres and API,
  verified interrupted status and durable progress, resumed the checkpoint, and
  confirmed the original recorded events were unchanged.
- Streamlit AppTest submitted a message to the live API and rendered the response
  without exceptions. This is a programmatic UI test, not a browser visual review.
- Pinecone Local container smoke test: known-vector upsert/query, metadata filter,
  namespace isolation, and fixture cleanup. No OpenAI calls or provider keys used.
- Remote Compose configuration validation: normal services are Postgres, migrate,
  API, UI, and HTTPS proxy; Pinecone Local is excluded unless explicitly opted in.
- Both Railway-style builds (`APP_TARGET=api` and `APP_TARGET=ui`) succeeded.
  Production API entrypoint ran as non-root on a configured port, passed readiness,
  and completed a streamed run against the isolated test database. UI runtime UID
  was also verified as non-root. Temporary verification containers were removed.
- Ruff lint/format checks and offline lockfile consistency check.

## Hosted checks still require configuration

- Hosted Pinecone: supply a Starter project API key; run the read-only smoke check.
- OpenAI: supply an API key; the provided smoke check lists models without generating text.
- LangSmith: supply a key/region, enable tracing, and run the trace smoke check.
  The check verifies two successes and one failure grouped by thread. Tracing
  code is present, but no upload to the user's account has been verified yet.
- No Railway resources, registry uploads, public URLs, DNS/TLS certificates, or
  remote backups were provisioned or tested. Remote deployment needs its own
  networking, streaming, and restore verification.

## Deliberate scope limits

The application has one mock node. It does not implement retrieval, an LLM answer,
RBAC/authentication, rate limiting, RLM research, or MCP yet. It supports one API
process, request-bound execution, and explicit checkpoint resume. It does not
provide background run recovery, atomic checkpoint/event writes, or exactly-once
tool side effects. The remote deployment files are preparation, not a claim that
the entire assignment is production-ready.
# Local observability extension — 2026-09-27

- Phoenix 20.16.0 started under Podman using pinned image digest
  `sha256:319d0f507183501cd42042c2490513d7f26ce03af00bfba2966e6a75229dc521`.
  Health endpoint and browser UI at localhost:6006 responded successfully.
- Backend runs as UID 10001 and writes valid JSONL to the host `var/logs` mount.
  Console output remains available. Unit checks cover rotation, append across
  logger restarts, queue overflow and runtime file-write failure.
- OpenInference 0.1.76 LangChain instrumentation and OTel 1.45.0 exported actual
  streamed mock runs to project `comtech-local`. Verified nested application,
  graph and node spans, input/output values, success/error status and conversation
  session grouping. Headless Edge rendered project rows and the trace detail tree.
- A live disconnected SSE run exported an interrupted root span. Explicit
  checkpoint resume exported a new completed trace with the prior run in metadata.
- Run records persist a distinct OTel trace ID; matching run/trace IDs appear in
  JSONL logs. Application UUID trace IDs retain their previous meaning.
- `scripts/verify_observability.py` passed: three synthetic success/failure runs,
  session grouping, replay equality, nested spans and persistent log correlation.
  `--verify-saved` passed after forced recreation of API and Phoenix containers.
- Stopped the actual Phoenix service: the API completed a mock run in about
  1.3 seconds and remained ready. `trace_export_failed` was persisted in JSONL.
  New traces arrived after Phoenix restarted. No guarantee is made about spans
  dropped during outages.
- SQLite online backup passed `PRAGMA integrity_check`. Restored its copy into
  a separate temporary Phoenix container and read 12 historical project spans
  through its REST API. Removed only that temporary container after verification.
- Inspected the active default retention policy: seven-day threshold, weekly
  cleanup cron. Did not wait seven days to validate scheduled deletion.
- Windows focused tests: **10 passed**. Linux container suite against isolated
  Postgres: **16 passed**, covering off/local modes, streaming, concurrency,
  failure, timeout, disconnection/resume, replay, masking and bounded shutdown.
- Ruff lint/format and Git whitespace checks passed. Final API/migration runtime
  images built from the lockfile; normal development, local observability and
  remote Compose configurations validated.
- No OpenAI/Pinecone calls or hosted LangSmith verification were performed for
  this extension. Standalone metrics storage, raw OTLP file archives and general
  browser log search remain outside scope. Local traces/logs use bounded queues
  and can lose buffered data on crashes or prolonged outages.
