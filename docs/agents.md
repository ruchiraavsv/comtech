# Enterprise agents

The opt-in enterprise graph implements Supervisor, Knowledge Worker, Reviewer,
and Final Answer Generator. Authorization and Research MCP analytics remain
deferred. The Research document broker and isolated Python runner are implemented;
the recursive Research loop and application integration remain pending. The default mock mode remains available.

## Run

Keep `OPENAI_API_KEY` and `PINECONE_API_KEY` in the gitignored `.env`. The published
release and original source store must exist together under `var/ingestion`.
The default build is `2fddb22824bee702`; no re-ingestion is required.

```powershell
uv sync --frozen --extra mcp
./scripts/compose.cmd -f compose.agents.yaml up --build -d
```

The overlay enables enterprise mode, mounts ingestion artifacts read-only, points
the API at Northstar MCP, and allows a 300-second request. The development UI is at
`http://localhost:8501`; `/health/ready` reports the selected mode. Startup validates
release/source checksums and MCP discovery schemas. Missing artifacts or credentials
fail explicitly. The API image contains the MCP client and cached tokenizers.

For a host-run API, set `AGENT_MODE=enterprise`, a reachable `AGENT_MCP_URL`, and
`INGESTION_ARTIFACT_ROOT`. Behind a Windows enterprise TLS proxy, prepopulate the
tokenizer with `.venv/Scripts/python.exe scripts/cache_agent_tokenizer.py`; it uses
system certificate trust and verifies tiktoken's pinned checksum. It never disables
TLS verification. To use mock mode, omit the agent overlay and use `AGENT_MODE=mock`.

## Model selection

| Role | Default | Reasoning effort |
| --- | --- | --- |
| Supervisor tool loop | `gpt-6-sol` | medium |
| Simple worker decisions | `gpt-6-luna` | none |
| Simple worker finalization | `gpt-6-luna` | low |
| Complex worker decisions/finalization | `gpt-6-sol` | low |
| Reviewer | `gpt-6-sol` | medium |
| Final wording | `gpt-6-luna` | none |

Supervisor marks factual lookups/simple chains as `simple`, and cross-document
synthesis, temporal comparisons, conflicts or causal analysis as `complex`.
Classification changes model capacity, never budgets or evidence requirements.

Role overrides are `SUPERVISOR_MODEL`, `KNOWLEDGE_WORKER_MODEL`,
`KNOWLEDGE_WORKER_COMPLEX_MODEL`, `REVIEWER_MODEL`, and `FINAL_ANSWER_MODEL`.
Precedence: role override, nonempty `OPENAI_MODEL`, then built-in defaults. No silent
model fallback occurs. Update `AGENT_TOKEN_ENCODING` and the conservative
`AGENT_MODEL_CONTEXT_WINDOW=128000` when selecting a different model family.

The choices follow the documented distinction between
[Sol's agentic reasoning](https://developers.openai.com/api/docs/models/gpt-6-sol)
and [Luna's focused work](https://developers.openai.com/api/docs/models/gpt-6-luna).
The Supervisor uses [Responses function calling](https://developers.openai.com/api/docs/guides/function-calling).
Other roles use [Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Both model names were verified against the configured account's model list.

## Runtime behavior

New turns use graph version 2: one Supervisor loop calls `knowledge_worker`, inspects
its results, and chooses further work or `submit_answer`. Independent calls can run
concurrently; dependent follow-ups wait for completed results. Review revisions
return to this same loop. Generic tool execution and the review/final gates remain
runtime nodes; planning and synthesis are no longer separate Supervisor states.
The loop permits at most `AGENT_MAX_TASKS + MAX_REVIEW_CYCLES + 2` model decisions;
the Reviewer remains capped at two evaluations. Exhaustion fails without publishing
an unapproved answer. Research/Python tools are not advertised.

Pending unversioned version-1 checkpoints finish on the retained legacy graph,
including its existing role prompts. Their next user turn starts on version 2.
New input cannot overwrite a pending run, and unknown graph versions fail explicitly.
Worker result readers distinguish unversioned legacy results from schema version 2.
R1 required no database or saved-checkpoint migration.

R2.1 adds application migration 3 for background run/objective identities, pinned
scope/deadlines, task/attempt leases, budget reservations, and execution/artifact
references. It preserves existing checkpoints and unversioned worker results.
New enterprise stream runs now use the API run ID in their graph/evidence records.
Legacy resumes retain their original graph identity. A database constraint enforces
one active run per conversation across both execution modes.

The internal background submission registry atomically creates the run, objective
and initial task. Reusing a key for the same thread/request returns the original
run, budget and deadlines; a different request conflicts. Background checkpoints cannot
fork a new run through legacy resume. Background execution is opt-in under
`BACKGROUND_ENABLED=true` with enterprise mode; it defaults off. Apply migrations 3 through 7
through the existing migration command/service when updating the application;
the implementation checks use an isolated test database, not the active stack.

R2.2 adds a PostgreSQL ledger with atomic reservations, protected root/worker
finalization capacity, immutable settlement and unique document-version counts.
Trusted accounting hooks cover all model roles/retries, logical worker calls,
embeddings and each source request. Repeated delivered rows/bytes count again;
internal source responses are not charged again as outer data delivery. Missing
provider usage stays reserved. Measured usage beyond a reservation blocks further
work and retains the receipt. Budget/deadline stops route workers to LLM
finalization; code never writes a semantic answer.

These hooks require a trusted fenced accounting context. R2.3 supplies task leases
and one shared resource owner within the API's singleton ownership lifetime.
Background graph identities must match that context. Ordinary
streams retain their existing local limits and retry behavior. Cancelled callers
leave in-flight resource slots owned until the underlying call settles; late
costs are recorded and cancelled/stale results are discarded. Durable call receipts
and startup reconciliation preserve these guarantees across background recovery.

R2.3 adds the internal durable queue and supervised consumers. Claims use monotonic
fencing; heartbeat renewals preserve it. Duplicate logical tasks and transition commits
cannot register different work under the same identity. Waiting continuations
release parent task slots. New terminal dependency results make parents ready,
including failures/cancellations, while self/ancestor/cross-branch cycles are
rejected. Ready continuations get priority over new tasks so a parent can assess
an early result. Child admission and finalization allocations commit atomically.

Consumers bind each continuation to the shared accounting resources and stop
semantic work on lease loss. Shutdown stops consumers, retains unresolved leases
for later reconciliation and waits for owned source calls to settle before releasing
API ownership. Persistence failures stop the supervised consumers and affect readiness.
When background mode is enabled, the ordinary reviewed graph runs under this scheduler.
Research defaults off. R6 supplies its private broker/runner dependency when
`RESEARCH_ENABLED=true`; the background Supervisor can then delegate to it.

Background clients submit `POST /api/runs` with `execution_mode: "background"`, a
stable `thread_id` and an `idempotency_key`. HTTP 202 returns the canonical run plus
its event/result URLs. Follow `GET /api/runs/{id}/events?follow=true` and reconnect
with the last event cursor; disconnect does not cancel execution. The connection
lifetime defaults to 60 seconds, separately from the 1,800-second objective deadline.
Status and stored reviewed results are available independently of the event stream.
Final task result, approved answer events and terminal status commit atomically.

`POST /api/runs/{id}/cancel` persists cancellation before signalling execution to
stop and is idempotent. Cancelled/completed/expired jobs cannot be resurrected.
Startup recovery retains the same run, objective, pinned sources, deadline and budget.
For active background jobs, `/resume` with the current canonical `checkpoint_id`
returns HTTP 202 for that same job; the durable scheduler owns continuation. A stale
or unrelated checkpoint is rejected. Legacy stream resume semantics remain intact.

Bounded model/tool outputs are recorded before graph advancement. Restart reuses
committed receipts and reconciles their costs before continuing a checkpoint. If an
external call was dispatched but no trustworthy completion record survived, recovery
terminates with `uncertain_external_completion` and retains its allowance. It does
not silently refund or retry unknown paid calls. This is conservative recovery,
not a provider exactly-once guarantee. Changed source versions and expired absolute
deadlines also terminate without new calls.

Research's first release is document-only (D01). Its document broker and
Python runner do not expose MCP tools. The existing Knowledge Worker retains all
seven Northstar lookups; the Supervisor can continue routing operational questions
there.

The default cumulative profile is 250,000 model tokens, with 24,000 protected for
top-level completion. A worker conservatively protects 120,000 tokens for its
bounded finalization/correction and provider attempts. Consequently this profile
admits one ordinary worker at a time even if local parallelism is two; after its
hold is released, the next independent worker can run. See spec section 8 for
the remaining counters and protected request/step capacity.

Research contracts and an evidence adapter now support registered computations and
child claim inheritance. Source bytes, hashes, observing task and source time stay
intact; exports include transitive premises. These interfaces have synthetic tests,
with durable registration, background jobs, the data broker, Python isolation and
the Research agent implemented in R2-R6. Follow the
[research implementation checkpoint](plans/recursive-research-implementation.md).

The worker receives knowledge search, bounded section reading, and the existing
seven MCP tools. Search queries dense and BM25 branches with matching semantic
filters, merges rankings, and returns attributable discovery snippets. Reading
selects sections within an exact document/version, or validates explicit section
IDs. Oversized sections return exact query-relevant Unicode spans, partial flags,
token counts and remaining span locators. Repeated narrower queries inspect other
content. Neither operation claims complete document or collection coverage.

The advertised `max_sections` maximum matches the configured reader limit for both
Knowledge Worker and Research, including Research's native model tools and SDK schema.
Invalid section counts/IDs return bounded correction guidance. Section reads may also
return up to eight query-ranked `section_options` (exact IDs and headings), fitted within
the existing response cap. These are navigation metadata, not inspected evidence;
`section_options_truncated` marks an incomplete directory. Use a more targeted query
when the directory omits a required section. Worker history and Research's last result
preserve these options without promoting headings into claims.
The pinned source manifest resolves exact IDs and their `DOC-` shorthand. Research
admission validates selectors before narrowing scope; unknown names produce correction
feedback instead of silently creating a task whose allowed population is empty. Reads
resolve the same shorthand before checking the allowed set; normalization grants no
additional document access.

```ini
MAX_SECTIONS_PER_READ=3
MAX_TOKENS_PER_SECTION=1000
MAX_TOKENS_PER_READ=3000
KNOWLEDGE_WORKER_MAX_CYCLES=5
TOTAL_CONTEXT_BUDGET=30000
FINALIZATION_RESERVE=4000
MAX_REVIEW_CYCLES=2
AGENT_MAX_TASKS=6
AGENT_PARALLEL_WORKERS=1
AGENT_TOOL_TIMEOUT_SECONDS=15
AGENT_WORKER_TIMEOUT_SECONDS=90
AGENT_MODEL_TIMEOUT_SECONDS=45
```

The read limit includes serialized result metadata, so a call may return less
than three full 1,000-token sections. Exploration has 26,000 tokens including
instructions, schemas, decisions, observations and framing headroom. Runtime
reserves each tool's bounded result before calling it and checks the result after.
An expansion that cannot fit is never executed. Runtime records the stopping
reason; the tool-free worker finalization LLM determines supported claims and
unresolved needs. Its prompt/output must fit the total budget and reserve.
A structurally invalid draft gets one bounded LLM correction attempt over the same observations; a second failure
ends execution without invented evidence or new retrieval.

Evidence materialization validates selected observation IDs and snapshots exactly
the observed content. IDs distinguish snippets, list summaries, detailed records
and individual spans. Evidence carries run/task identity, source version, content
hash and relevant times. Operational facts are current at the frozen MCP snapshot,
not the machine date. Failed tools never provide invented replacement evidence.

Reviewer sees only the package, structured results and selected evidence. It has
no retrieval tools. At most two Reviewer evaluations permit one repair opportunity;
Supervisor can repair synthesis or schedule bounded follow-up workers. A second
rejection fails without emitting an unapproved factual answer. Final wording sees
only the approved package and evidence; runtime adds validated citations and
reviewed limitations, unresolved needs, conflicts and clarification.

Set `AGENT_PARALLEL_WORKERS=2` to run independent objectives concurrently. Each
worker has its own budget; task dependencies and the overall task/request limits
remain enforced. New turns reset work state while retaining conversation history.
Checkpoint recovery retains completed worker cycles. Read-only calls may repeat
if interrupted before their checkpoint commits; exactly-once calls are not promised.
Model transient failures get at most two attempts through LangGraph retry policy;
tool failures can be retried by the worker within its existing cycles.

Activity events include stages, tools, selected models, cycles, token estimates,
usage, errors and stopping reasons. Raw observations and worker scratch messages
are not emitted as answer text. Internal checkpoints/traces still retain workflow
state; this is not an authorization or redaction system. Citation checks verify
structure, not semantic entailment; semantic fidelity needs model evaluation.

## Research data broker (R3)

R3 adds the document-access backend and migration 7; it does not advertise Research
or Python tools to the Supervisor. Direct Research tools and the Python SDK share
Knowledge Worker's `knowledge_search` and `read_document_sections` schemas and
retrieval implementation. Direct reads require no Python execution. Ordinary MCP
tools remain available only to Knowledge Worker.

The broker additionally supports `describe`, `enumerate_documents`, `read_spans`,
`read_artifact` and `write_artifact`. Enumeration uses verified published metadata;
search results remain bounded discovery. Metadata counts establish document-version
totals, not incident totals or semantic matches. Exact spans have explicit character
ranges and continuation; unknown metadata stays unknown. Source pins, immutable
task scope, current lease/capability, opaque cursors and shared budget checks apply
to every request. Capability management and inheritance grants are trusted-only.

Result pages cap at 64 KiB; span pages default to 4,000 characters and cap at 8,000.
Shared document token limits also apply after durable evidence IDs are added.
JSON/Parquet artifacts retain input, code and environment lineage, verified hashes,
and a 32 MiB output cap per execution. Reading another task's artifact requires an
explicit grant and sufficient scope for its complete input lineage. Source paths,
arbitrary SQL/network access, provider keys and executable serialization are absent
from the SDK. Typed failures include scope/pin mismatch, invalid or expired refs,
hash mismatch, timeout and source unavailability; failed calls supply no facts.

Active objectives protect stored evidence. Final selection can retain an artifact's
input closure for 30 days; other records use seven-day retention. Maintenance
tombstones expired records before deleting managed files and can recover orphaned
writes. R6 connects reviewed final selection and scheduled maintenance to the application.

`uv sync --frozen --extra mcp --extra research` installs the broker's pinned PyArrow
dependency. The isolated test target includes this extra. R4 supplies the isolated
runner and execution transport described below. R5 supplies the recursive agent
loop, and R6 completes application integration, including the trusted broker service
and API-owned fixed embedding operation.

## Restricted Python runner (R4)

The runner has no network interface. A protected Unix socket connects trusted
control to a single-slot supervisor; generated Python gets only an inherited data
channel. The supervisor is UID 10000, generated code UID 10002 with cleared
capabilities. Seccomp and Landlock restrictions apply before numerical imports,
including to library threads. Process creation, shell execution, new sockets and
writes outside the temporary workspace are denied. Numerical threads remain
bounded and inherit the same restrictions.

The image pins Python 3.12.14, NumPy 2.5.3, pandas 3.0.6 and PyArrow 25.0.1.
It has no application source store, provider keys/SDKs, package installer or
container-runtime socket. Code assigns its JSON-compatible output to `result`;
large data uses the existing SDK's JSON/Parquet artifact operations.

Each attempt records code/input/environment hashes and shared usage. Duplicate
committed requests reuse results; interruption is not permission to rerun an
unknown calculation. Cancellation, lease loss and control disconnect stop the
process and clean its workspace. Logs remain separate from model-visible results.
Retention hooks remove expired logs/code while preserving computation manifests;
R6 schedules maintenance and connects final evidence selection.

The tested limits are 120 seconds wall time, 60 seconds CPU, 16 generated tasks
(threads count), 64 descriptors, 16 KiB per output stream, 64 KiB code and 3,000
result tokens. Additional address space after trusted library initialization is
capped at 512 MiB. Container limits independently enforce 2 CPU, 2 GiB memory,
64 PIDs, read-only root and 64 MiB temporary storage. Artifact limits remain R3's.

The isolated acceptance profile mounts current source/tests into the **test client**;
the runner contains only its built minimal image. Initialize its dedicated control
volume once, then run the suite:

```powershell
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml build
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml run --rm --no-deps control-init
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml up --no-build --abort-on-container-exit --exit-code-from tests
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml down
```

Acceptance targets Podman on the local Linux VM. Docker and remote targets remain
unverified. The host-orchestrated restart test is opt-in separately; its test prints
`RESTART_READY` before the operator restarts only `python-runner`. Research remains
disabled by default; this test profile does not deploy or enable the application feature.

## Recursive Research (R5)

Research receives the original user message alongside the delegated objective, from
the durable application run. This context clarifies intent without broadening source
scope. The Reviewer also receives the original user wording. Prompts honor explicit
Research requests, distinguish required gaps from optional context, and call for
finalization as soon as the requested finding is supported. These are model-behavior
instructions, not a deterministic guarantee of early stopping.

Python decisions receive `sdk_results` alongside request schemas. In particular,
enumeration totals are at `page['coverage']['total_count']`, while dataset descriptions
put `total_count` at the top level. A missing/null validation input is an unavailable
check, not a successful check. Method prose must agree with observed check outcomes.
Enumeration's advertised version policy is restricted to the task's pinned policy.
Python results retain bounded `data_errors` from the broker, including operation, code
and corrective message, even when the runner reports only `DataError`. Successful source
receipts survive a later Python failure; artifacts from that failed execution do not
become available computation evidence. The existing 3,000-token result cap still applies.
Oversized generated results also retain bounded successful source receipts, with an omitted
receipt count if necessary. Batched reads should return compact IDs/counts because registered
source text enters the next Research decision automatically.

Supervisor and Reviewer receive source text once in the top-level evidence map, with duplicate
text omitted from model-facing Research envelopes. Stored envelopes and provenance remain intact.
Final wording receives the approved answer package; runtime validation and citation rendering
use the full evidence. An unaffordable child proposal returns corrective feedback without creating
tasks, allowing a smaller batch, a targeted read or finalization within the unchanged limits.
Failed/cancelled specialist tasks return a claim-free unresolved result to Supervisor. Their
unvalidated drafts and evidence are excluded; independently validated completed work remains
available for review. A failed follow-up is not evidence that a source or control is absent.

Provider input uses a model-only projection: source content, identifiers, locators, effective/as-of
dates and partial-read information remain, while durable audit IDs/hashes and duplicate native
tool schemas are omitted. Input-size estimation uses this same projection; complete stored records
remain authoritative for provenance and replay. Invalid answer citation selections receive precise
claim-level feedback and one structural correction before semantic review; persistent invalid
packages never publish. This does not increase the two-review cap or any token limit.

Final citations group document excerpts by source/version/as-of, retaining exact section and
character locators. Operational queries with different content or filters stay distinct, with
their query scope displayed. Computations retain execution/result/hash/coverage references and
grouped source locators; their complete registered input lists remain in the durable artifacts.

Exhausted provider credits/quota now raise `ProviderQuotaExhausted` rather than consuming transient
rate-limit retries. The opt-in 30-case harness stops subsequent submissions on that error. Genuine
transient rate limits retain the existing bounded retry behavior.

R5 provides the recursive Research implementation through
`research.agent.ResearchAgent` and `research.specialist.ResearchSpecialist`. Its direct
search/read shapes match Knowledge Worker; Python and recursive child proposals are additional
capabilities. Parents and children can use any available action without a mandatory corpus scan.
Evidence sufficiency can end exploration after the first useful result. No-progress, cycle,
context, depth, objective-budget and deadline stops route to a tool-free LLM finalizer.

Each Research task uses the existing PostgreSQL queue, fenced attempts, shared ledger and
task-specific LangGraph checkpoints. It reserves 60,000 cumulative tokens for its finalizer and
one correction/provider retry at the default 30,000-token context ceiling. Actual calls settle
actual usage; unused capacity is released on completion. Source/artifact input grants are
explicit, and selected inherited findings preserve their originating task and exact source spans.
Analysis artifacts include runtime-recorded model/prompt identity, method, units, assumptions,
input closure and verified hashes. Calculation lineage does not establish semantic correctness.

Claim validation reports the offending claim IDs and fields together. Worker and Research
corrections receive the rejected draft and those issues, reuse existing evidence, and remain
bounded to two finalization attempts and the existing ledger allowance. Integrity/provenance
failures still fail closed. Metadata description and new enumeration coverage count as discovery
progress; new receipt IDs alone do not. Individual document handles remain available in durable
lineage without expanding into separate model-facing findings. Finalization context trimming
prefers removing query metadata before calculation artifacts.

Python can attach an optional `analysis_process` to `data.write_artifact(...)`. It contains
`summary` (a concise prose account of the procedure actually executed), `population` (scope and
count unit), `checks` (checks performed with outcomes in the saved result), and `limitations`.
This documents a reproducible method, not private reasoning. It stays in the immutable artifact
metadata alongside the registered input references and execution; it is not standalone source
evidence. Existing artifacts without this field remain readable.

For example, a document census can describe enumerating all pages, deduplicating by
`(document_id, version)`, mapping missing types to `unknown`, grouping by type and reconciling
the total. Its result should store the counts, rows read, unique identities and check outcomes.
Copy the relevant `data.receipt_refs` after reading inputs and before calling `write_artifact`;
those receipts can register the inputs even when all retrieval and calculation occur in one call.
Return a compact result and `artifact_ref`; Python locals do not persist across executions.

The Reviewer receives each computation's method/process, bounded result, execution metadata
and input coverage. Page counts, enumeration positions, continuation cursors and truncation are
preserved. A final page alone cannot establish that earlier pages were processed. The prose is
author-reported and cannot override those records or establish correctness by itself. Valid
aggregate/reduction claims can cite `computation_ref` without a verbatim source sentence or
invented premise claims. Complete metadata counts do not require semantic reading of document
contents; content classifications still need inspected spans and explicit extraction uncertainty.

`build_supervisor_graph(..., research=ResearchSpecialist(agent))` is the tested opt-in integration
boundary. The Supervisor yields its scheduler slot while Research runs, then continues through
validation, Reviewer and final rendering. Reviewer repair consumes the same objective budget.
The final wording model still receives only the approved package and evidence.

The application factory supplies this dependency only with the R6 opt-in configuration below.
Research MCP access remains deferred. Scripted acceptance verifies control/provenance and known
calculations; hosted model quality and Docker deployment remain unverified.

## Opt-in application integration (R6)

Use one API process and one private broker. The API owns all model calls and a fixed
query-embedding endpoint pinned to the source release's model/dimensions. The broker owns
read-only source access, artifacts and the Unix runner connection. Private HTTP calls require
`RESEARCH_SERVICE_TOKEN` (at least 32 random characters), current fenced leases and registered
source scope. Generated Python never receives that service token. The broker image rejects an
OpenAI key; its Compose environment is explicit and does not load the application `.env` file.
The shared service token is internal transport authentication, not the deferred user RBAC feature.

Set `DATABASE_URL`, `PINECONE_API_KEY`, `AGENT_BUILD_ID`, model credentials and the private token
in the existing local environment. Deploy the matching published release and source store under
`var/ingestion`. API and broker must use matching read limits and source pins. Do not enable this
overlay on Railway or an unaccepted runtime. For the accepted local Podman target:

```powershell
podman compose -f compose.yaml -f compose.dev.yaml -f compose.agents.yaml -f compose.research.yaml run --rm --no-deps research-init
podman compose -f compose.yaml -f compose.dev.yaml -f compose.agents.yaml -f compose.research.yaml up --build -d
```

These are deployment commands for an explicitly selected application stack; acceptance does not
run them against an existing installation. The initializer only sets ownership on the two named
volume roots. Keep `research-artifacts` and PostgreSQL together in backups; do not use `down --volumes`
on a stack whose research results must survive. Broker and runner have no published ports. Runner
has no network or source/artifact mounts; the broker mounts sources read-only and a separate durable
artifact volume. Readiness checks broker, runner environment, source pin, tool limits and database.
No healthy response is fabricated when a required service is unavailable.

The UI discovers background support, submits with one stable idempotency key and stores conversation,
run and event cursor in the URL. Reload/reconnect reads the same run without resubmission. Ambiguous
submission acknowledgements retain the exact request for retry within the browser session; after
reload use saved runs, or retry the original question with the retained submission key. Cancel is
explicit; closing the browser does not cancel. Only the committed reviewed result is displayed as
answer text. The legacy stream path stays available when background mode is disabled.

`GET /api/runs/{id}` reports bounded task/mode, source-version, selected-evidence counts and cumulative
used/reserved/protected/ceiling counters. Activity events carry task/attempt identity and termination
status without source content, code, capabilities or provider secrets. Research forces trace input
and output redaction. Optional tracing upload failure does not replace the durable ledger/audit.

Migration 8 adds 30-day final-result expiry; result and event endpoints then return 410. Scheduled
maintenance defaults to 300 seconds, expires stored run/task output and Research checkpoints, prunes
24-hour logs and seven-day code/working artifacts, and retains selected evidence input closures for
30 days. Active evidence is protected. Durations are fixed in this release; only the maintenance
interval is configurable. Conversation checkpoints and audit metadata have separate retention and
are not erased by this operation; this is not complete conversation/data deletion.

The isolated acceptance suite uses `compose.test.yaml` + `compose.runner-test.yaml`. The optional
`compose.research-test.yaml` adds the real broker image with synthetic metadata and no provider keys:

```powershell
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml -f compose.research-test.yaml build tests research-broker
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml run --rm --no-deps control-init
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml up -d postgres python-runner
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml -f compose.research-test.yaml run --rm --no-deps broker-fixtures
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml -f compose.research-test.yaml up -d research-broker
podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml run --rm --no-deps tests uv run --frozen --no-sync pytest -q -p no:cacheprovider
```

Hosted acceptance is separately gated by `RUN_HOSTED_RESEARCH=1` and
`HOSTED_RESEARCH_API_URL`, against a configured opt-in stack. Run
`pytest tests/research/test_hosted_application.py -q`; it submits four bounded ordinary, semantic,
deterministic and mixed requests and writes result/route/usage reports to
`var/research-evaluation` (override `HOSTED_RESEARCH_REPORT_DIR`). It makes paid calls and transmits
retrieved content. Reports require human review of semantic support, unknown classifications,
scope/coverage, arithmetic and whether exploration stopped appropriately. A schema/test pass is
not a semantic-quality pass. This hosted run has not yet been performed for R6.

An additional [complex evaluation suite](research-evaluation.md) provides 30 scenarios / 33 turns
across Knowledge Worker, semantic/deterministic/mixed Research, cross-worker questions and source
limitations. Its separate opt-in is `RUN_HOSTED_COMPLEX=1`; run
`pytest tests/research/test_hosted_complex.py -q` against the same configured API. The catalogue
includes per-case review rubrics and failure criteria. The 2026-10-02 live baseline finished with
**3 passed and 27 failed**; see [results and remediation priorities](research-evaluation-results-2026-10-02.md).
This does not establish general Research acceptance or replace the still-unrun four-case smoke suite.

## Checks

```powershell
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider
podman compose -p comtech-agent-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
podman compose -p comtech-agent-tests -f compose.test.yaml down
```

Offline/container tests use fake models, synthetic long documents, real local MCP
transport, and isolated PostgreSQL. They make no paid calls. Windows pytest may
need a writable temporary directory outside a restrictive sandbox.

Explicitly opt-in hosted checks make paid OpenAI embedding/model calls, read-only
Pinecone queries and send retrieved fictional content to OpenAI. They never create
or update indexes, account plans or source data.

```powershell
$env:RUN_AGENT_HOSTED_TESTS='1'
.venv/Scripts/python.exe -m pytest tests/retrieval/test_sources.py::test_published_hosted_discovery_smoke tests/agents/test_hosted.py -q
```

Successful operational/documentary/mixed runs save reports under
`var/agents-validation/`. This small suite does not replace the full golden
evaluation set. See [phase tasks and validation status](plans/enterprise-agents-implementation.md).
