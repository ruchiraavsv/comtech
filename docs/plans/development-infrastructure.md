# Development infrastructure plan

Status: proposed implementation plan, revised 2026-09-27 after deployment discussion. Infrastructure implementation and public deployment have not started.

## Scope and first milestone

Build the development foundation for the AI Lead Technical Assessment. Start with `START -> mock_node -> END`; the async mock node emits progress and returns a deterministic message. No real retrieval or model invocation is required for this milestone.

Prove that Streamlit receives updates before execution finishes, graph state survives an API restart, recorded events can be replayed without executing the graph, and a real execution appears in LangSmith when credentials are supplied.

Keep the scaffold small. Full agent routing, recursive research, ingestion, hybrid ranking, production authentication, analysis tools, MCP, and public deployment are later work. Preserve extension points for them without implementing placeholders that imply those features already work.

## Agreed architecture

```text
Browser <-> Streamlit
                |
                | HTTP requests / SSE response
                v
          FastAPI + LangGraph
                |
                +-- PostgreSQL: checkpoints, run records, event log
                +-- LangSmith hosted: execution traces
                +-- Pinecone hosted Starter: demo vector database
                +-- Pinecone Local: vector integration tests only
                +-- OpenAI: configured for later model integration
```

- FastAPI owns orchestration and backend credentials. Streamlit renders conversation and activity events.
- PostgreSQL and Pinecone are separate integrations. Do not put checkpoints or event history in the vector database.
- Local development uses Podman on Windows. Commit portable Compose configuration that also works with Docker Compose for reviewers and later deployment.
- Railway Git-based deployment is the preferred hosted-demo path. Prepare deployable images and configuration now; actual account provisioning and public deployment remain later work.

## 1. Repository and reproducible dependencies

- Initialize Git in this project after confirming the repository boundary; maintain small commits for each implemented milestone.
- Add README setup instructions, `.gitignore`, `.dockerignore`, `.env.example`, `pyproject.toml`, a committed dependency lockfile, and an explicit supported Python version.
- Prefer Python 3.12 with uv for dependency management; verify the chosen LangGraph, LangSmith, AG-UI, Pinecone, and checkpointer versions together before locking them.
- Build reproducible backend and UI images from the lockfile. Containerized execution must not require host Python to match the project version.
- Make runtime images suitable for remote deployment: non-root execution, no development reload or source mounts, configurable listen ports, health checks, and graceful shutdown. Inject secrets at runtime; never copy `.env` or bake keys into image layers.
- Suggested layout: `src/comtech/api`, `src/comtech/graph`, `src/comtech/events`, `src/comtech/integrations`, `src/comtech/settings`, `ui`, `tests`, `scripts`, and `docs`.
- Keep dependencies limited to this milestone; include provider integrations only where setup or a meaningful smoke check uses them.

## 2. Podman and Compose compatibility

Observed on this PC: Podman 5.8.2 and Git are available; Docker and standalone `podman-compose` were not found on PATH. Sandbox inspection could not determine machine readiness: `podman machine list` failed on a machine lockfile permission, and `podman compose version` failed resolving the configured machine connection. These are unresolved environment checks, not proof that Podman is broken or a Compose provider is absent.

- Inspect the existing Podman machine, connection, and Compose provider under appropriate permissions. Reuse the existing machine; do not reset it or delete unrelated containers/volumes.
- `podman compose` delegates to an external provider. Verify the provider; if missing, install/configure a compatible provider and document its version. Docker Desktop is not required.
- Add `scripts/compose.ps1`, a thin argument-forwarding wrapper defaulting to Podman, with explicit Docker selection for other machines. It should report missing providers or stopped machines clearly, preserve exit codes, and avoid modifying global configuration implicitly.
- Add a preflight command for engine connectivity, provider availability, required configuration, and port conflicts. Print no secret values.
- Define `api`, `ui`, and `postgres` as normal services, and `pinecone-local` behind a `vector-test` profile. Pin appropriate image versions/digests during implementation.
- Keep `compose.yaml` as the portable base, `compose.dev.yaml` for development mounts/commands/localhost ports, and `compose.remote.yaml` for a Linux-host deployment with restart policies and HTTPS reverse proxy configuration. The local wrapper explicitly selects base + development files; document base + remote commands separately so development settings cannot leak into deployment.
- Keep Pinecone Local opt-in and absent from the normal remote deployment. Production-mode configuration must reject a local-emulator target. The test profile must explicitly configure test consumers to use the emulator; starting its container alone does not switch application targets.
- Use a named Postgres data volume, container DNS names for inter-service traffic, and localhost-bound development ports. Avoid host networking and Docker-socket mounts.
- Check Pinecone Local's Linux/amd64 image compatibility in the Podman VM. Keep test index dimensions aligned with test vectors.
- Implement health checks and bounded application startup retries; do not rely solely on provider-specific dependency ordering behavior.
- Ordinary stop/restart commands must retain data. Document volume deletion as a separate explicit reset command.

Planned commands, to validate against the actual provider:

```powershell
./scripts/compose.ps1 up --build -d
./scripts/compose.ps1 logs -f api
./scripts/compose.ps1 --profile vector-test up -d
./scripts/compose.ps1 down
```

## 3. Async backend and streaming contract

- Use FastAPI lifespan management for shared clients and database pools, with clean shutdown. Use native async I/O; move unavoidable blocking operations off the event loop.
- Begin with one API worker. Serialize active runs per conversation, allowing different conversations to execute concurrently. Document that process-local coordination is not sufficient for multiple workers.
- Use an async LangGraph execution/streaming API supported by the pinned version. The mock node emits progress around asynchronous waits and returns deterministic state.
- Expose an initial POST run endpoint that streams SSE. Streamlit consumes it with an HTTP streaming client; browser-native EventSource is not required for this POST flow.
- Use AG-UI Python event models and encoding where practical: run lifecycle, step lifecycle, text messages, and custom progress. Validate exact package APIs while scaffolding. Avoid exposing raw graph state or debug events.
- Store a run record and assign a run ID before execution. Associate it with the conversation/thread and request ID.
- Persist each application event before sending it, ordered by a per-run sequence number. Put a stable event cursor in the SSE `id` field. Client rendering must tolerate duplicate delivery.
- Provide a read-only saved-event endpoint with cursor-based replay. Support explicit cursor input for the Python client and `Last-Event-ID` for SSE consumers where applicable.
- Initial execution remains request-bound. A disconnected client cancels active work; reconnecting replays persisted events but does not silently restart execution. Preserve checkpoints and expose explicit resume/re-execution as a separate operation.
- Add keepalive pings, request/dependency timeouts, bounded buffering, cancellation cleanup, and terminal success/error events when the connection remains writable. Do not swallow task cancellation.
- Automatic background continuation and crash recovery scheduling are deferred. On restart, reconcile stale running records as interrupted rather than claiming they completed.

## 4. Durable state and replay

- Use official `langgraph-checkpoint-postgres` / `AsyncPostgresSaver`. Let the library own checkpoint tables and serialization, initialized through its supported setup mechanism.
- Use LangGraph `thread_id`, checkpoint IDs, async state/history access, and checkpoint resume APIs. Choose synchronous checkpoint durability at execution boundaries if supported by the pinned release.
- Manage application-owned `runs` and `run_events` tables separately with a small versioned migration mechanism. Event rows contain run ID, sequence, timestamp, schema version, and AG-UI JSON payload.
- Keep application run IDs and LangSmith trace IDs explicitly mapped; do not assume framework IDs are interchangeable.
- Saved-event replay is exact playback of recorded application events and makes no graph/model calls. Checkpoint replay is new execution from a saved boundary and may repeat subsequent side effects.
- A one-node graph cannot resume at arbitrary lines inside that node. A crash before node completion can require re-executing the node.
- Checkpoint storage and event storage are not one atomic transaction. Document this limitation; do not claim exactly-once execution. Future external side effects will need idempotency and explicit recovery design.
- Retain development history across restarts; document an explicit cleanup/reset path and leave production retention policy for deployment work.

## 5. LangSmith from the first node

- Use hosted LangSmith observability; no LangSmith deployment runtime is required.
- Separate `comtech-dev` and `comtech-demo` projects. Match the endpoint to the account region, and configure workspace selection when required.
- Trace every demo execution (sampling 1.0). Disable external tracing in ordinary automated tests; provide an opt-in hosted smoke test.
- Use native LangGraph traces, adding custom spans only for operations that need independent visibility. Record thread, run, request, environment, and code-version metadata.
- Capture synthetic mock inputs/outputs; never include secrets or authorization headers in state, logs, or trace metadata. Define a masking boundary before real organizational data is introduced.
- Correlate structured logs and run records with trace IDs. Gracefully flush pending uploads during shutdown using the pinned SDK's supported mechanism.
- Tracing outages should be visible in logs but should not fail otherwise successful application execution. Missing required demo configuration should be reported clearly.
- Verify a successful mock run, a deliberate failure, and two executions grouped under one conversation. Verify recorded-event playback does not create another agent-execution trace.

## 6. Pinecone and OpenAI configuration

- Hosted demo uses Pinecone Starter with a project API key. Assume the user can provide Pinecone and OpenAI keys when integration checks require them; store these in ignored local configuration or hosting secrets. Key availability does not block the mock scaffold.
- Keep hosted and local target selection explicit. Tests must not accidentally write to the hosted demo index; use isolated test index/namespace identifiers.
- Pinecone Local requires no genuine credential and has no persistence across stops. It is an emulator, not a production database. Verify SDK/API compatibility with its supported API version.
- Do not create a hosted index until embedding dimensions, metric, and dense/sparse strategy are decided. This milestone can validate hosted credentials/connectivity without indexing documents.
- Add OpenAI configuration without calling a model from the mock graph. Assume a key will be supplied; keep model selection configurable and defer embeddings/model decisions to retrieval implementation.

Expected configuration groups:

```dotenv
APP_ENV=development
DATABASE_URL=
API_BASE_URL=http://api:8000

LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=comtech-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_TRACING_SAMPLING_RATE=1.0
# LANGSMITH_WORKSPACE_ID=

PINECONE_MODE=hosted
PINECONE_API_KEY=
PINECONE_INDEX_NAME=
PINECONE_INDEX_HOST=
# PINECONE_LOCAL_HOST=  # Set by the test profile for the selected emulator mode

OPENAI_API_KEY=
OPENAI_MODEL=
```

Final variable names and defaults will be validated against the implementation. Demo configuration enables tracing explicitly; the default scaffold must run with no external API keys.

## 7. Health, logging, and frontend

- `/health/live`: process liveness, no external API calls.
- `/health/ready`: initialized application and usable required Postgres connection. Optional hosted services are reported separately; do not bill model calls or contact every provider on each probe.
- JSON logs include timestamp, severity, event, request ID, conversation ID, run ID, and trace ID when available. Log exceptions with context but sanitize secrets.
- Streamlit displays incremental activity, deterministic mock answer, terminal status, and a way to reload recorded history. Clearly label mock execution.
- Keep domain work in the backend; do not place database or provider credentials in browser-visible content.

## 8. Deployment preparation

Preferred path: push source to GitHub, connect Railway services to the repository, and let Railway build the API and UI Dockerfiles and run the resulting container images. Railway handles image storage for this source-build flow; Docker Hub, GHCR, a registry subscription, and a CI image-publishing pipeline are not prerequisites. Podman remains sufficient on the development PC.

| Component | Local | Hosted demo |
| --- | --- | --- |
| API and UI | Podman Compose builds | Railway builds from the same Dockerfiles |
| Postgres | Container with named volume | Railway Postgres service with persistent storage |
| Pinecone | Local emulator for tests; hosted integration opt-in | Hosted Pinecone Starter |
| OpenAI | Mock graph initially; opt-in real calls later | API integration when implemented |
| LangSmith | Optional hosted tracing | Hosted tracing enabled |

- Document Railway service build paths/targets, start commands, health checks, runtime variables, and resource sizing assumptions. Railway service configuration replaces Compose orchestration on that platform; do not assume every Compose setting is automatically applied.
- Public HTTPS ingress goes to Streamlit. Streamlit calls FastAPI over private networking; Postgres also remains private. Keep server-to-server SSE incremental and verify the browser-to-Streamlit connection works on the deployed platform.
- Start with one API replica and one worker. Do not enable horizontal scaling while run coordination and interrupted-run reconciliation assume a single process. Account for deployment overlap before enabling rolling deployments.
- Run database/checkpointer initialization in a controlled deployment step before serving traffic. Document backups and restore responsibility for persisted checkpoint and event data.
- Provide a remote environment example with placeholders and validation for required settings. Do not provide working shared credentials or development database passwords as remote defaults.
- Keep the remote Compose option for a Linux host: production runtime commands, persistent Postgres, only the HTTPS proxy publicly exposed, streaming without proxy buffering, appropriate timeouts, and a documented domain/TLS setup. This is deployment preparation, not a claim that production security and operations are complete.
- Validate the remote Compose configuration and runtime images locally where possible. Explicitly record that actual remote networking, HTTPS, platform behavior, and backup restoration need verification at deployment time.
- Publishing prebuilt images to GHCR is an optional later alternative for CI-controlled releases or a Compose host. If adopted, use immutable release tags/digests; do not introduce it as a dependency now.
- Before public exposure, complete the assignment's authentication, authorization, and rate limits and configure provider spending limits. These remain outside the mock infrastructure milestone.

## Implementation sequence and acceptance checks

1. Bootstrap repository, lock dependencies, and establish Podman wrapper/preflight. Verify Compose configuration and image builds on this PC.
2. Start Postgres, API, and UI. Verify health checks and JSON logs. Confirm ordinary restart preserves the named volume.
3. Add one-node async graph, official Postgres checkpointer, and AG-UI/SSE adapter. Verify the first progress event arrives before completion and concurrent conversations do not block each other.
4. Add durable run/event recording and read-only replay. Verify event ordering, cursor reconnect without duplicate rendering, restart persistence, and playback without graph execution.
5. Verify interruption/resume semantics: stop the API during the mock node, restart, inspect saved state, and explicitly resume from a valid checkpoint. Record that the node can rerun.
6. Enable opt-in LangSmith smoke checks with user credentials. Verify successful, failed, and grouped conversation traces.
7. Verify Pinecone Local under the test profile with a tiny upsert/query/delete integration check; separately verify hosted connectivity when a key is supplied.
8. Validate production runtime images and both development and remote Compose configurations. Prepare Railway setup instructions without provisioning paid services or deploying the app. Confirm the normal remote configuration excludes Pinecone Local and development reload/mounts.
9. Document exact setup commands, service responsibilities, troubleshooting, limitations, and credential setup. Commit coherent milestones without secrets or generated runtime data.

Use focused tests for streaming-before-completion, checkpoint persistence, event replay, cancellation, and target isolation. Real provider tests are explicit opt-in checks, not requirements for ordinary unit tests.

## User inputs needed during implementation

- Pinecone Starter project API key: assumed available from the user, supplied locally when hosted verification is needed.
- LangSmith API key and account region; workspace ID if required.
- OpenAI key: assumed available from the user for later real model integration, not needed for this mock milestone.
- Any Podman machine/provider setup requiring elevated host changes will be identified from preflight evidence before making those changes.

## Reference documentation

- Assignment: `Lead AI Assignment.pdf` in the repository root.
- Podman Compose provider behavior: https://docs.podman.io/en/latest/markdown/podman-compose.1.html
- LangGraph checkpointers: https://docs.langchain.com/oss/python/langgraph/checkpointers
- LangGraph replay semantics: https://docs.langchain.com/oss/python/langgraph/use-time-travel
- LangGraph streaming: https://docs.langchain.com/oss/python/langgraph/streaming
- AG-UI events: https://docs.ag-ui.com/concepts/events
- FastAPI SSE: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- LangSmith setup: https://docs.langchain.com/langsmith/trace-with-langgraph
- Pinecone Local limitations: https://docs.pinecone.io/guides/operations/local-development
- Pinecone API keys: https://docs.pinecone.io/guides/projects/manage-api-keys
- Railway Compose-to-services deployment guide: https://docs.railway.com/guides/docker-compose
