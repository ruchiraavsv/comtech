# Recursive research implementation plan

**Status:** R0-R5 complete with scripted models; R6.1-R6.4 accepted on the local Linux/Podman target. R6.5 complex live baseline: 3 passed / 27 failed; remediation and acceptance remain open. Background and Research default off; Research MCP remains deferred (D01).  
**Created:** 2026-09-30.  
**Technical authority:** [Recursive research implementation specification](../../recursive_research_agent_implementation_spec.md), proposed v1.1 including evidence-sufficiency updates.  
**Baseline:** [Completed enterprise agent implementation](enterprise-agents-implementation.md).

This plan turns the technical specification into ordered, reviewable changes to the existing Comtech application. It is also the execution record: update task status, decisions, validation and the current checkpoint here so another executor can continue from the repository without relying on chat history. The specification defines intended behavior; this plan defines implementation order and completion evidence.

## Executor instructions

Before the first implementation task, read the technical specification in full, this plan, and [existing agent operation](../agents.md). Inspect the current code and working-tree changes; the repository already contains staged, modified and untracked work. Preserve that work and do not reset or assume an untracked file is disposable.

Before each task or resumed session:

1. Read **Current execution checkpoint**, **Decision record** and the latest **Execution log** below.
2. Read the linked specification sections for the active phase and any sections changed since the last recorded revision. The plan is not a substitute for the technical document.
3. Inspect the relevant implementation and tests. Distinguish already implemented behavior, intended changes and genuine gaps; older milestone docs sometimes describe the previous mock scaffold.
4. Choose the next dependency-ready task. Record its ID as active and identify the files it will change. Keep a working slice small enough to verify and hand off.
5. Implement the task and run the checks appropriate to its behavior. Mark it complete only when its outcome and acceptance checks pass; record failures or skipped checks explicitly.
6. Update the checkpoint and append a concise execution-log entry before ending a session or moving to the next phase. Preserve exact remaining work, not just “continue implementation.”

If user decisions change scope, update the specification and this plan together and record the affected task IDs. If code differs from the intended design, record the difference and implement the intended behavior; do not silently rewrite the spec to describe an accidental implementation. Routine implementation choices can be resolved and recorded without creating a new approval gate.

After context compaction, use this same resume procedure. Reuse valid completed work and checks; repeat them only when relevant changes, failures or unresolved risks justify it. Keep secrets, raw source prose and hidden evaluation answers out of the plan/log.

## Scope carried into every phase

- One Supervisor agent loop selects the existing Knowledge Worker or the new Recursive Research specialist. Research has semantic, deterministic and mixed modes; semantic reasoning stays in agent calls, while Python performs brokered retrieval/computation.
- Research parents/children also use direct `knowledge_search` and `read_document_sections` with the Knowledge Worker's existing argument/result shapes (D05). Shared retrieval, restricted Python and recursive discovery are independently available within scope/budget; none requires the others first.
- Research can finish from existing evidence, one useful result or an early child result. Recursion, Python and corpus enumeration are optional capabilities. Require population coverage only where the requested conclusion depends on it.
- Preserve the ordinary worker's bounded ReAct behavior, exact source provenance, independent Reviewer, two-review cap and final-only answer publication.
- Background research survives browser disconnects and process restarts. Recovery retains canonical identity, source versions, deadlines, usage and selected evidence.
- Reuse LangGraph and existing PostgreSQL. Add transactional task/budget/execution records where needed; no new message bus, Redis dependency or alternative conversation history.
- Keep per-context limits distinct from shared cumulative usage and concurrency. Reserve finalization tokens, request/step capacity and time.
- Authorization/RBAC remains deferred. Source capability enforcement and generated-code isolation are required; no production multi-tenant security claim is made.
- Research uses existing published documents. Northstar MCP remains available only to the ordinary Knowledge Worker (D01). Do not regenerate/index the corpus, inspect private canonical/evaluation files as research sources, or assume transaction/telemetry/warehouse data exists.
- Research remains disabled until its dependent components pass their acceptance checks. Default mock mode and legacy streaming remain supported. Local Compose is the initial execution target; deployment is a separate action.

## Phase order and dependencies

| Phase | Deliverable | Prerequisite | Demonstrable exit |
| --- | --- | --- | --- |
| R0 | Baseline and execution context | None | Current behavior, scope and next task recorded |
| R1 | Supervisor loop and compatible contracts | R0 | Ordinary Knowledge Worker route adapts between results and still passes review |
| R2 | Durable jobs and shared accounting | R1 | A scripted background run survives reconnect/restart without fresh budget |
| R3 | Broker, source access and artifacts | R2 contracts/ledger | Targeted reads and scoped analysis inputs have attributable coverage |
| R4 | Isolated Python execution | R3 broker/control contracts | Bounded calculation executes through the broker with verified isolation |
| R5 | Recursive semantic and mixed research | R2–R4 accepted | Research returns validated findings, including early completion and partial results |
| R6 | Application integration and acceptance | R1–R5 accepted | UI/API complete ordinary, semantic, deterministic and mixed flows with recovery |

Finish phases in this order by default. Independent work may overlap after interfaces are settled—for example, runner image preparation alongside broker adapter work—but integration checks still follow the dependencies. Assign clear file ownership when parallel work touches shared contracts, database migrations or API lifecycle code. No phase boundary requires a separate user confirmation unless a genuinely unresolved scope decision affects that work.

Within each phase, execute tasks in numeric order unless a recorded dependency analysis identifies independent work. A conditional task recorded as deferred does not block the next applicable task. Distinguish implementation, validation and feature enablement in the log; completing an interface does not enable the capability behind it.

## R0 Baseline and implementation context

Read: [decisions][S1], [routing][S2], [sources][S3], [boundaries][S4], [remaining decisions][S14], [agent operation](../agents.md), and the completed enterprise plan. Inspect `src/comtech/agents/`, `api/app.py`, `db.py`, `events.py`, `settings.py`, the MCP/retrieval adapters, Compose files and existing tests.

- [x] **R0.1 Record the baseline.** Capture the current code revision plus relevant uncommitted work, specification revision/hash, existing graph/API lifecycle and published source identities. Run the relevant existing offline/container baseline once when implementation starts. Record actual results rather than copying historical pass counts.
- [x] **R0.2 Establish the working contract.** Record the existing public/checkpoint contracts to preserve and resolve routine choices for schema versioning and module boundaries. Carry the optional MCP collection-query decision as D01; do not block unrelated work on it. Select R1.1 as the next task once the baseline is usable.

Exit: an executor can identify what already works, what must change and which sources are in scope without reopening the conversation. No runtime behavior changes are needed for R0.

## R1 Supervisor loop and compatible contracts

Read: [routing][S2], [contracts and evidence][S5], [state and replay][S7], [failure semantics][S11]. In particular inspect spec sections 5.3–5.5 before changing result validation.

Primary files: existing `src/comtech/agents/{graph,contracts,model,evidence,runtime}.py`; new research contracts as needed; `tests/agents/` and contract tests under `tests/research/`.

- [x] **R1.1 Define versioned delegation and result contracts.** Add typed specialist selection, Research modes, objective/task inputs, conditional coverage metadata and the result envelope. Preserve ordinary `KnowledgeTask` complexity semantics. Separate semantic status, stop reason and scheduling state. Check old result parsing and targeted answers with unknown corpus totals.
- [x] **R1.2 Extend evidence compatibility.** Define computation/query/artifact references and child-claim export/inheritance without fake root observations. Implement validation and rendering against synthetic registered records; preserve original observing task, exact content/hash, source time and transitive premises. Reject forged/missing/cyclic references and test ordinary evidence unchanged.
- [x] **R1.3 Implement the Supervisor agent loop.** Replace the bespoke plan/dispatch/synthesize progression with bounded model/tool turns, generic execution and typed answer-package submission. Expose the existing Knowledge Worker; describe Research only when its capability is available. Verify that one worker result can alter the next task and that independent calls obey concurrency limits.
- [x] **R1.4 Preserve review and conversation behavior.** Return Reviewer revisions to the same Supervisor loop, keep the two-evaluation cap and final-answer gate, reset only new-turn state, and preserve recoverable state on resume. Record how graph/schema versions handle existing pending checkpoints: tested compatibility or explicit version-aware legacy handling, never silent reinterpretation.
- [x] **R1.5 Accept the ordinary workflow.** Run document-only, MCP-only, mixed-source, clarification, worker partial-result, targeted repair, exhausted review and checkpoint-resume regressions. Confirm no Research/Python capability is advertised prematurely and no internal draft becomes an answer event.

Exit: the Supervisor can adapt its work after each specialist result while existing Knowledge Worker, citation and review guarantees remain intact. The Research interface is defined, but its implementation is still disabled.

## R2 Durable jobs and shared accounting

Read: [scheduler/state][S7], [budgets][S8], [background lifecycle][S10], [errors/retention][S11]. Revisit spec sections 7.4 and 10.4 before implementing retry/resume behavior.

Primary files: `src/comtech/db.py`, `migrate.py`, `api/app.py`, `events.py`, `settings.py`; new `research/{scheduler,ledger,registry}.py`; real PostgreSQL tests.

- [x] **R2.1 Add migrations and trusted identity.** Persist run mode/lifecycle, objective mapping, task/attempt leases, reservation and execution/artifact identities. Bind API/graph/objective IDs explicitly. Add durable per-thread active-run and submission-idempotency constraints. Test upgrade from existing tables and old result/checkpoint records; keep application migrations separate from LangGraph's schema.
- [x] **R2.2 Implement the atomic ledger.** Reserve/consume/release across all branches; preserve token, model-request, control-step and time capacity for finalization/review. Account for ordinary workers, Supervisor, Reviewer, final wording, retries, embeddings, logical data calls and underlying source fan-out without double counting. Race the last available reservation and test uncertain in-flight usage conservatively.
- [x] **R2.3 Implement claims and background continuations.** Add fenced task leases, claim dedupe, waiting/ready transitions and idempotent result registration under the existing singleton API owner. Release parent execution slots when waiting for queued work or children. Never hold database connections/transactions across external calls; retain resource slots until the corresponding in-flight operation settles. Use a fake specialist to exercise continuations; recursive admission is completed in R5.
- [x] **R2.4 Separate submission from event delivery.** Add background submission returning HTTP 202, persistent idempotency keys, replay-follow events, run/result status and atomic terminal-answer publication. Preserve legacy streaming and cursor validation. Test that disconnect/reconnect or duplicate submission neither restarts execution nor duplicates the final answer.
- [x] **R2.5 Implement cancellation and restart recovery.** Recover background leases instead of blanket interruption, retain deadlines/usage/source pins, and reconcile uncertain executions before retry. Reject stale commits and invalid cross-run checkpoints. Explicit cancel stops new work; browser disconnect does not. Preserve legacy resume without allowing it to fork a background budget.
- [x] **R2.6 Accept durable execution.** With real isolated PostgreSQL and scripted models, exercise crash points around claim, tool/result commit, checkpoint and final event; API shutdown/restart; concurrent thread admission; expiration during downtime; and repeated cancel/resume requests. Record the tested recovery boundaries and any at-least-once external-call limitations.

Exit: a background ordinary/fake-research workflow completes or terminates correctly without a browser connection, and recovery cannot mint new budget. Python termination and full Research recovery will be integrated and retested after R4/R5.

## R3 Broker source access and coverage

Read: [actual sources][S3], [trust boundary][S4], [broker/coverage][S6], [accounting][S8], [artifact behavior][S9]. Coverage must reflect the claim's needs, including valid early answers and scoped aggregates.

Primary files: new `research/{broker,adapters,artifacts,coverage,data_sdk}.py`; existing retrieval and MCP adapters; relevant settings and service wiring; focused source/ledger tests.

- [x] **R3.1 Establish broker contracts and capability enforcement.** Implement trusted execution capabilities, immutable source scope plus narrower requests, schema/field/operator checks, bounded requests and usage settlement. Separate management/control operations from execution data access. Include child/artifact scope inheritance and reject forged refs/cursors or attempts to broaden a scope.
- [x] **R3.2 Reuse targeted source access.** Share `knowledge_search` / `SearchArgs` / `ToolResult` and `read_document_sections` / `ReadArgs` / `ReadDocumentSectionsResult` with Knowledge Worker. Reuse the underlying implementation for direct Research calls and Python SDK access; direct calls require no Python execution but still enforce trusted scope, pins, evidence registration and shared budgets (D05). Research MCP access is deferred under D01; reject those capabilities explicitly and preserve existing Knowledge Worker MCP tools. Keep ordinary worker tool allowlists separate from additional research capabilities. Provide the API-owned fixed embedding operation with pinned model/dimensions and ledger charging; no model/provider credential enters generated code. Test schema parity, exact errors, source versions, document truncation and backend fan-out accounting.
- [x] **R3.3 Add document enumeration and deterministic span reading.** Use verified published manifests, version policies, stable pagination and exact section/character references. Preserve existing relevance-oriented Knowledge Worker reads. Support a targeted lookup without corpus enumeration and scoped enumeration/aggregate evidence where the conclusion needs it; test long spans, version/event dedupe and incomplete pages.
- [x] **R3.4 Implement durable artifacts and lineage.** Store immutable bounded JSON/Parquet results, input/query/code/environment hashes, registered selections and coverage in separate research storage. Safely load by capability and reject executable formats, stale/expired refs and mismatched hashes. Implement retention that preserves active/referenced evidence according to the spec.
- [ ] **R3.5 Deferred: Research MCP collection queries (D01).** The user deferred all Research MCP access on 2026-10-01. This extension is outside the first release. If included, add advertised/versioned describe/query operations over the validated snapshot, typed filters/aggregates/pagination and declared relationships. Preserve the ordinary seven-tool surface and test old/new server discovery. If deferred, record that outcome and test clear unavailable-capability behavior; do not read fixture files directly through the broker.
- [x] **R3.6 Accept source and coverage behavior.** Verify targeted facts, selected-record calculations, samples and population results each carry suitable provenance. Test authoritative scoped aggregates without transferring every row, unknown/null handling, source outages, restricted artifact inheritance and the prohibition on turning top-k discovery into an unsupported global conclusion.

Exit: the broker provides bounded usable inputs with truthful provenance and coverage. Deferred MCP access is visible and does not prevent document analysis or the separate Knowledge Worker MCP lookups. Broker endpoints do not provide arbitrary network, SQL or private-file access.

## R4 Isolated Python execution

Read: [component boundaries][S4], [SDK][S6], [Python runtime][S9], [deployment][S12], [acceptance matrix][S13]. Before building the runner service, resolve D02 using a small host/runtime feasibility check for control transport, UID separation, network enforcement and descendant containment. Record the outcome before proceeding with the implementation; configuration names alone do not establish feasibility.

Primary files: new `research/{runner,runner_client,data_sdk}.py`; broker control transport; `Dockerfile`, proposed `compose.research.yaml`, locked dependencies and container tests.

- [x] **R4.1 Build the minimal runtime.** Add the Python 3.12 runner target with pinned SDK/analytics dependencies, non-root execution, bounded temporary workspace and fresh subprocess per call. Keep provider secrets, application/source mounts and runtime package installation out. Verify the image's actual environment, identity and installed dependencies.
- [x] **R4.2 Implement brokered execution and results.** Bind code/purpose/input refs to trusted execution/attempt IDs and capabilities. Allow multiple bounded SDK calls per execution, compact result/evidence refs and durable artifact continuation. Test a calculation with known inputs/output and replay of committed results without rerunning Python.
- [x] **R4.3 Enforce network and process boundaries.** Implement the chosen narrow control transport and runner-to-broker access without exposing the default application network. Enforce CPU/wall/memory/PID/disk/output limits and terminate every execution descendant, including escaped sessions. Verify controls from generated code under the actual Linux container runtime; `python -I` is not the boundary.
- [x] **R4.4 Connect cancellation and crash reconciliation.** Tie run deadlines/cancel to runner capabilities/processes, settle uncertain usage and discard late/stale commits. Verify workspace cleanup and recovery after runner/container restart. Generated code must never fall back to in-process execution or direct source access.
- [x] **R4.5 Accept the execution boundary.** Run the spec's network/secret/forged-capability/resource/process adversarial cases, successful brokered retrieval/calculation, artifact resume and broker-unavailable cases. Record measured limits and Docker/target Podman results separately, including skipped or unavailable runtime checks; an untested runtime remains unverified. Leave Research disabled on a target where the required boundary is not demonstrated.

Exit: a deterministic calculation can execute through the isolated runner and return registered, reproducible evidence. The required sandbox/resource/cancellation behavior has been tested, rather than inferred from Compose settings.

## R5 Recursive semantic and mixed research

Read: [routing and sufficiency][S2], [agent/result/prompt contracts][S5], [task lifecycle/dedupe][S7], [budgets][S8], [worked flows][S14]. Recheck sections 6.4 and 7.1 when deciding whether to launch or wait for more work.

Primary files: new `research/{coordinator,task_graph,scheduler,registry,coverage}.py`; existing model, evidence and runtime integration; scripted graph tests and research fixtures.

- [x] **R5.1 Implement the research task loop.** Support direct shared search/expansion, bounded execute-Python, delegate and finalize actions, compact referenced context and versioned prompts (D05). Parents and children can discover, expand, delegate or compute according to remaining gaps; do not require Python before direct retrieval or recursion. Permit immediate finalization from sufficient existing evidence or the first useful result. Preserve local context limits and mode selection; semantic work happens in model calls, not inside Python's SDK.
- [x] **R5.2 Add recursive admission and joining.** Validate inherited/narrower scopes, gap/partition identity, depth/fan-out, task dedupe and shared reservations. Reject self/ancestor/cross-branch wait cycles. Release slots before child work and wake parents for useful results or terminal failures, without deadlocking on all planned children.
- [x] **R5.3 Implement completion and stopping.** Reassess sufficiency before more work, retire unnecessary queued/running branches while protecting shared dependencies, and reject late changes to approved results. Enforce no-progress/cycle/budget/deadline control. Keep semantic status independent: unread optional material or a failed irrelevant branch does not force `partial`.
- [x] **R5.4 Implement semantic and mixed analysis.** Interpret bounded source partitions with supporting spans and uncertainty; aggregate registered extractions deterministically where needed. Preserve unknown classifications, event/version dedupe, scope, units and calculation assumptions. Do not require partitioning/full collection processing for answers that already have adequate support.
- [x] **R5.5 Integrate the specialist result and review path.** Export the selected child/root claim closure through the R1 adapter, resolve inherited evidence/computations and return it to Supervisor. Connect shared ledgers to all nested model/tool/finalizer calls. Reviewer repair can request additional necessary work within the same budget; final rendering handles computed citations.
- [x] **R5.6 Accept the Research modes.** Test early supported completion, multi-step investigation, useful recursion, deterministic calculation, semantic classification plus aggregation, partial required coverage, unavailable capability, duplicate/cyclic proposals, child failure, cancellation, recovery and review rejection. Verify no unnecessary calls after sufficiency and no unsupported promotion of partial populations.

Exit: all three Research modes return compatible reviewed evidence/results, with recursion and complete-population work only when useful to the question. At this point enable Research only in the isolated acceptance profile for R6.

## R6 Application acceptance and operation

Read: [background interfaces][S10], [observability/retention][S11], [packaging][S12], [complete acceptance criteria][S13]. Use the ordinary and Research worked flows in [section 14][S14] as behavior examples, not hard-coded answers.

Primary files: `ui/app.py`, `api/app.py`, `events.py`, `settings.py`, Compose/Docker configuration, operation docs and integration tests.

- [x] **R6.1 Complete the background UI flow.** Submit once, persist run/cursor, follow or reconnect to progress, show stored final output and support explicit cancel. Browser reload must recover the same run; internal code, raw data and unreviewed claims do not become answer text. Verify a short ordinary answer works through the same background interface.
- [x] **R6.2 Integrate bounded observability and retention.** Add route/mode, queue/task/execution identity, coverage, usage and stopping fields to existing activity/traces without exposing payloads/secrets. Test tracing outage independently of durable accounting. Test artifact/result expiry and preservation of active evidence.
- [x] **R6.3 Package the opt-in stack.** Complete the research Compose overlay, broker source-store mount, separate durable artifact volume, health/readiness, feature discovery, configuration and service lifecycle. Verify ordinary/mock operation with research disabled and research operation with it enabled. Record unsupported remote/runtime targets rather than treating local Compose checks as Railway certification.
- [x] **R6.4 Run end-to-end recovery and boundary acceptance.** Exercise all four routes through real API/PostgreSQL/broker/runner and scripted models, including model/tool outage, replay/live delivery, cancel, API/runner restart, concurrency, early completion, partial answers and final-answer uniqueness. Run existing relevant regression suites and lint/format checks after integration.
- [ ] **R6.5 Evaluate hosted behavior and finish the handoff.** Run a small opt-in live-provider suite when its scope/configuration is available; record actual routes, citations, usage, coverage and stop behavior separately from scripted tests. Evaluate semantic extraction/answer quality, not only schema validity. Update operation/configuration docs, known limits, task/phase records and final next steps. A skipped hosted check stays explicitly pending or is recorded as an agreed deferral.

Exit: all applicable tasks and required checks are complete, operation docs describe the actual behavior, and evidence supports each claimed capability. No public deployment, index mutation or corpus regeneration is part of this plan.

## Specification coverage map

Use this map during phase review to catch requirements that fall between components. It points to the technical document rather than copying its schemas and numerical defaults here.

| Spec sections | Primary tasks |
| --- | --- |
| 1–4 decisions, routes, sources and boundaries | R0.1–R0.2, R1.3, R3.1–R3.2, R4.3 |
| 5 contracts, claim inheritance and prompts | R1.1–R1.4, R3.4, R5.1, R5.4–R5.5 |
| 6 SDK, source capabilities and answer-appropriate coverage | R3.1–R3.6, R4.2, R5.4 |
| 7 recursion, ownership, dedupe and recovery | R2.1, R2.3, R2.5–R2.6, R5.2–R5.3 |
| 8 shared budgets, local context and protected finalization | R2.2, R3.2, R4.4, R5.1–R5.3, R5.5 |
| 9 Python execution, artifacts and isolation | R3.4, R4.1–R4.5 |
| 10 background API, events, cancel, resume and UI | R2.1, R2.3–R2.6, R6.1, R6.4 |
| 11 failures, telemetry and retention | R2.2, R2.5, R3.4, R4.4, R5.3, R6.2 |
| 12 service and repository integration | R4.1, R4.3, R6.3 |
| 13 acceptance and adversarial scenarios | Phase exit checks, R4.5, R5.6, R6.4–R6.5 |
| 14 examples and remaining scope | R0.2, R3.5, R5.6, R6.5 |

## Validation and completion rules

Use tests that exercise contracts or failure modes; do not create tests merely mirroring a reversible edit. Prefer fake models and generated fixtures for repeatable routing/budget/evidence checks, real isolated PostgreSQL for atomicity/recovery, and real Linux containers for runner isolation. Hosted semantic checks supplement these tests; they do not replace them.

Run targeted tests during a task, the relevant phase checks at its exit, and the integrated suite in R6. Record the exact command, environment, code revision/working state and outcome. A skipped check is not a pass. Do not repeatedly rerun broad suites after documentation-only or unrelated changes.

Existing commands that executors can reuse before new test targets are introduced:

```powershell
.venv/Scripts/python.exe -m pytest tests/agents tests/retrieval -q -p no:cacheprovider
podman compose -p comtech-research-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
podman compose -p comtech-research-tests -f compose.test.yaml down
```

Use an isolated project/database; the existing test Compose file does not yet test a research broker/runner. Add the appropriate isolated profile in R4/R6 and record its actual command. Do not reset the user's active stack or remove persistent data to obtain a clean test run.

A task is done when its implementation, applicable checks and handoff record agree. Mark a phase complete only after its applicable task and exit checks pass. Disabling the feature is a safe way to preserve existing behavior while work is incomplete; it is not evidence that the new capability works.

## Decision record

Confirmed direction: Supervisor tool loop; durable background research; semantic reasoning in agents with scheduler-managed child tasks; brokered Python; evidence-sufficient early completion; authorization deferred. Do not ask executors to re-confirm these decisions.

| ID | Decision | Status and consequence |
| --- | --- | --- |
| D01 | MCP access in the first Research release | Deferred by user on 2026-10-01: do not add MCP access to the new Research Agent yet. Research starts with documents and document-derived analysis. Existing Knowledge Worker retains its seven MCP lookups and Supervisor can route operational questions there. R3.2 research MCP brokering and R3.5 collection queries are deferred; document work continues |
| D05 | Research direct search/expansion plus recursive discovery and restricted Python | Confirmed by user on 2026-10-01. Share the Knowledge Worker's search/read argument and result shapes. Direct Research retrieval does not require Python; scope, pins, evidence registration and shared accounting still apply. Parents/children may use all three capabilities as needed. Supersedes the former Python-only data-tool wording in spec sections 5.2/6.1; affects R3.1-R3.2 and R5.1/R5.6 |
| D02 | Broker/runner control transport and descendant containment on the target host | R4 choice: network_mode none; protected Unix control socket; generated-code SDK uses an inherited channel relayed by the trusted client into the R3 broker. Supervisor UID 10000, generated UID 10002 (separate from app services at UID 10001), explicit capability clearing and pre-import seccomp/Landlock. New sockets/processes/exec are denied; same-process threads inherit the boundary and have a 16-task ceiling. Numerical pools default to one. Full Podman boundary and restart acceptance passed; Docker remains unverified. The control volume has a separate initializer. No generated-code access to management or a general API |
| D03 | Versioned checkpoint/result migration strategy | R1: new turns use graph version 2; pending unversioned v1 checkpoints resume on the retained v1 builder. Unknown versions and overwriting pending runs fail explicitly. Results without a version parse as legacy; extended results require schema version 2. R2.1 migration 3 adds durable identities with nullable historical mappings, canonical new graph run IDs, objective-aware checkpoint validation and legacy-resume guards; old checkpoints are not rewritten |
| D04 | Budget/resource/retention tuning | R2.2 retains the spec's cumulative ceilings; adds 160 control steps and explicit protected root capacity: 10 model requests/control steps, 4 Supervisor steps and 5 retries. Each ordinary worker protects four local context allowances (120,000 tokens by default), 4 requests/steps and 2 retries for bounded finalization/correction. This permits one worker at a time under the initial token ceiling; pending work may run after settled holds release. Spec section 8 and ledger/graph tests record the behavior. Research admission and retention tuning remain later tasks |

If D01 is deferred, mark R3.5 as deferred with the decision reference rather than checking it as implemented. The core plan can complete without that optional extension, but the final capability summary and tests must state the limitation.

## Phase status

| Phase | Status | Completed tasks | Validation record |
| --- | --- | --- | --- |
| R0 | Complete | R0.1-R0.2 | Fresh offline baseline: 31 passed, 4 hosted skipped |
| R1 | Complete | R1.1-R1.5 | Windows: 117 passed/12 skipped; Linux with PostgreSQL: 125 passed/4 hosted skipped; lint/format passed |
| R2 | Complete | R2.1-R2.6 | Linux/PostgreSQL: 175 passed/4 hosted skipped; Ruff lint/format passed |
| R3 | Complete | R3.1-R3.4, R3.6; R3.5 deferred | Linux/PostgreSQL: 191 passed/4 hosted skipped; lint/format and lock validation passed |
| R4 | Complete on Podman; Docker unverified | R4.1-R4.5 | Full suite: 206 passed/5 skipped; separate restart and final syscall tests passed; lint/format/lock checks passed |
| R5 | Complete on Podman with scripted models | R5.1-R5.6 | Full suite: 226 passed/5 skipped; final focused checks: 27 passed; lint/format/whitespace passed |
| R6 | Local scripted implementation accepted; live remediation required | R6.1-R6.4 | Offline full suite 246 passed/9 skipped; complex live baseline 3 passed/27 failed; R6.5 open |

## Current execution checkpoint

Update this compact block at every handoff; keep detailed history in the log below.

| Field | Current value |
| --- | --- |
| Last update | 2026-10-04 - Credits restored; full optimized-build catalogue completed: 22 automated passes / 8 failures across all 33 turns; additional RS12 factual error found in source inspection |
| Technical baseline | Spec v1.2 with optional analytical-process evidence; SHA256 `6A67E3CB948933D7F740957442EAD01A011672F8D243E4BCCB5F3ABDA99351B1` |
| Current implementation state | Opt-in background Supervisor connects Research through authenticated private broker HTTP; fixed embeddings and all models stay API-owned. Document/Python/recursive paths, durable jobs, UI reload/cancel, selected evidence retention and maintenance are integrated. Defaults stay off |
| Active task | R6.5: full 30-case rerun and inspection complete; optimized app retained healthy/idle. Acceptance remains open because eight cases failed and RS12 conflated incident/publication dates |
| Next task | Address shared reference/lineage contracts first: valid ID selection, computation citation namespaces, ownership checks consistent across package validation/export/rendering, and partial-span JSON normalization. Then preserve compact artifacts through context trimming/review and improve coverage/retrieval planning |
| Completed task IDs | R0.1-R0.2, R1.1-R1.5, R2.1-R2.6, R3.1-R3.4, R3.6, R4.1-R4.5, R5.1-R5.6, R6.1-R6.4; R3.5 deferred (D01); R6.5 pending |
| Open scope | D01 resolved: Research MCP access deferred; existing Knowledge Worker MCP unchanged |
| Files changed in this slice | Rerun reports, read-only audit/analysis helpers and documentation only; no application edits or image changes during the batch. Numerical limits, spec and source pins unchanged |
| Latest checks | Optimized hosted catalogue: 22 passed/8 failed in 3579.98s, all 33 turns attempted; 160 exact document observations/hashes and 24 operational observations verified. Recorded model tokens 3,070,324; matched successful turns 448,420 to 433,434 (-3.34%). Prior isolated regression 159 passed/4 skipped remains prior validation |
| Known failures or blockers | KW02/XW25 invalid IDs; RD16 citation namespace correction; RD17 oversized mapping/review exhaustion; RD18 context loss, tuple/list mismatch and budget exhaustion; RM22 validation/render ownership disagreement; RM23 granted-artifact inheritance rejection; RM24 retrieval/recovery without required calculation. RS12 additional date error. No quota blocker observed. Four-case smoke, remote/Docker and latest-build restart remain unverified |
| Running processes or external changes | Retained comtech-complex-eval stack on localhost 18000/18501, zero active jobs/tasks. API d6ee62bc3929, broker 1c030d954807, runner 54b285f3eef4. Source pins/data and numerical limits unchanged; final image IDs saved in complex-2026-10-04-optimization/environment.json |
| Exact next action | Read the latest remediation section and complex-2026-10-04-optimized-full diagnostics/review_notes. Reproduce the shared contract failures locally before targeted fixes and live reruns; preserve this immutable build comparison and use a new directory for any future hosted batch. Do not rerun run_optimized_full.py into its populated directory |

## Execution log

Append one entry for a meaningful completed slice or handoff. Keep it concise and reference stable task IDs and repository files; do not paste raw tool output or conversations.

Initial entry — 2026-09-30: plan created from technical spec v1.1 and the current application. No research implementation tasks performed. D01 remains conditional. Next task: R0.1.


### 2026-09-30 - R0 baseline and R1 implementation

- Baseline: HEAD `a3f7a274857bcf89030435b853ee709c7e20b481`, with existing staged agent modules and substantial modified/untracked API, UI, MCP, retrieval, ingestion, tests and documentation work preserved. Read spec v1.1 (initial SHA256 `D0017D1DA05867A156384E4234A7C7F63F0FC5A443CFE9239D0734005E0C18F8`), the plan, current operation docs and active code; R1 consulted sections 2, 5, 7 and 11. No source story/private canonical/evaluation content was inspected.
- Existing source identity: published build `2fddb22824bee702` (132 documents, 1,054 sections/passages); Northstar snapshot `DEMO-2026-09-15-A`, as of `2026-09-15T10:00:00Z`, with seven bounded lookup tools. Search remains top-k discovery, not exhaustive population evidence.
- R0.1 baseline command: `.venv/Scripts/python.exe -m pytest tests/agents tests/retrieval -q -p no:cacheprovider`: **31 passed, 4 hosted skipped** after approved rerun with writable Windows temporary directories. Initial sandbox execution had 9 temporary-directory setup errors, 22 passes and 4 skips; these were environment failures, not assertion failures.
- R0.2 preserved contracts: `KnowledgeTask.complexity`, legacy result parsing, worker budgets/ReAct behavior, exact observations, two-review gate, final-only streaming, conversation messages, existing API routes and mock mode. New research types live under `src/comtech/research`; graph orchestration lives in `agents/supervisor.py`. Ordinary claim/answer types add only optional `computation_ref`; ordinary workers cannot register computations. D01 stays conditional.
- R1.1/R1.2: typed/versioned delegation, modes, objective/task/scope/coverage and result envelopes; explicit legacy/extended result reader; query/execution/artifact lineage and registered export of transitive child claims. Registry validation checks ownership, hashes, premises and computation inputs/results. Copies preserve original evidence ownership and prevent mutation through exported objects. In-memory registry is a tested interface boundary, **not durable storage or a research runtime**; R2/R3 provide durable registration.
- R1.3/R1.4: native Responses function tools `knowledge_worker`/`submit_answer`; bounded adaptive Supervisor loop with worker fan-out; revisions return to the same loop. No Research/Python tool is exposed. D03 uses explicit v1/v2 graph selection; a test interrupts a v1 worker, resumes it through the new factory without repeating its lookup, then starts a v2 conversation turn. Unknown checkpoint versions and overwriting pending work are rejected. Calls are independent bounded model decisions over checkpointed application state (`store=False`), not provider-side conversation state.
- Validation: `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider`: **117 passed, 12 skipped** on Windows (4 hosted plus 8 PostgreSQL-dependent integration cases). Focused new/agent tests: **37 passed** before the full run. `.venv/Scripts/ruff.exe check src/comtech/agents src/comtech/research tests/agents tests/research` and corresponding `format --check`: passed. Source-route regressions use synthetic document/MCP observations; real source adapters retain their existing tests.
- R1.5 pending isolated Linux/PostgreSQL command: `podman compose -p comtech-research-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests`. No paid provider calls were made; hosted semantic evaluation remains outstanding. Next: collect result, stop isolated containers, then R2.1.


### 2026-09-30 - R1.5 acceptance complete

The isolated Linux/Podman command above completed successfully: **125 passed, 4 hosted skipped in 33.21s**, including the real PostgreSQL/API integration cases skipped on Windows. Image `ce67a7cf587a1ac55cebe1670187329ea6973152dee6d82f279050b3a65eaa5b`; no code changed during its build/test run. `podman compose -p comtech-research-tests -f compose.test.yaml down` removed its containers/network after exit. Ruff lint/format and `git diff --check` passed. Existing mock/enterprise API behavior, source adapters, final-only streaming and checkpoint tests pass with the new loop. These results validate R1; they do not certify the future R4 Python sandbox or hosted answer quality.

The spec header/current-state table and agent operation docs now reflect R1; intended R2-R6 behavior is unchanged. The checkpoint records the updated spec hash. R0 and R1 are complete. New enterprise turns use Supervisor v2; research execution remains disabled. R2.1 is next. No database migrations, paid model calls, deployment or source/index mutations were performed in this slice.


### 2026-10-01 - R2.1 database and identity foundation (acceptance in progress)

- Read the execution checkpoint and specification sections 7, 8, 10 and 11; inspected the existing API/SSE lifecycle, database migrations, graph state, worker and source-call boundaries. Starting spec hash: `FC01E21555FCBDACF950603ECC777074B4CE08DA984EC61D723633F3DD3A1E42`. Existing staged/uncommitted work was preserved.
- Added application migration 3 in `research/schema.py`: run execution mode and canonical graph mapping; background objective scope/source pins/deadlines; initial queue/task and fenced-attempt fields; counters/reservations; execution/artifact identity references. LangGraph tables are untouched. Historical rows remain stream-mode with unknown graph identity rather than fabricated mappings; event sequence is backfilled from existing events.
- Added `JobRegistry.submit` as a trusted internal transaction, not an HTTP feature: run + objective + initial Supervisor task commit together. Per-thread idempotency binds the original request body; replay returns the same run, scope and deadlines. A PostgreSQL unique index prevents overlapping stream/background runs, including recoverable interrupted background jobs. Foreign keys reject cross-objective/task attempt, reservation, execution and artifact references.
- New enterprise streams bind graph/evidence run IDs to API run IDs. Checkpoint validation compares canonical run, objective, thread and graph version. Legacy resumes retain original graph identity; background parents/checkpoints are rejected by the legacy resume path so recovery cannot mint a separate run/budget. Startup reconciliation only interrupts stream jobs; background ownership recovery belongs to R2.5.
- Implemented state: database foundation and internal submission. Not enabled: background HTTP API, queue consumers, ledger operations/call accounting, cancel/recovery, recursive admission, broker or Python. The schema supplies persistence, not a claim that these later behaviors work. R2.2 must initialize/protect/settle shared budgets before R2.3/R2.4 enable execution.
- Validation so far: Linux full suite **131 passed, 4 hosted skipped** (`podman compose -p comtech-research-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests`). Windows targeted graph/contracts suite: **24 passed, 6 PostgreSQL tests skipped**. Added final ownership/API guard tests are being checked separately with real PostgreSQL. The initial focused console-script invocation failed collection because it did not place the shared `tests` package on the import path; the corrected command uses `uv run --frozen --no-sync python -m pytest`. No application assertions ran in that failed invocation. Focused Ruff lint and format checks plus `git diff --check` pass.
- No hosted calls, source inspection/regeneration, active-stack migration or deployment. Migrations ran only in isolated PostgreSQL; tests create and remove uniquely named test schemas. D01 stays conditional. D03 now includes nullable historical identity and explicit new-run mapping.
- Next: finish ownership/admission checks, remove the isolated stack, and start R2.2's atomic ledger and per-call integration. At recovery implementation, distinguish a durable initial queue entry from a fully initialized graph checkpoint; never infer checkpoint ownership merely from thread identity.


### 2026-10-01 - R2.1 accepted

- Final command: `podman compose -p comtech-research-tests -f compose.test.yaml run --build --rm tests uv run --frozen --no-sync python -m pytest tests/research/test_registry.py tests/test_integration.py -q`: **17 passed in 25.06s**, using image `c86b451795fb500baf08e695c4a6f49be539171c1f8e2ebb3016d7aa43e2d4de`. This covers all seven registry/upgrade/ownership tests and ten API integration cases (tracing off/Phoenix). The final constraint preserves the conversation slot for interrupted background jobs. Earlier full Linux run: **131 passed, 4 hosted skipped** before the final added guards/tests.
- Checks: `.venv/Scripts/ruff.exe check src/comtech/research src/comtech/db.py src/comtech/api/app.py src/comtech/agents/supervisor.py tests/research tests/test_integration.py`, corresponding `format --check`, and `git diff --check` passed. No code changed after the final focused image was built. Spec and operation docs describe R2.1 groundwork and remaining runtime work; current spec hash is in the checkpoint.
- Cleanup: `podman compose -p comtech-research-tests -f compose.test.yaml down` removed the isolated containers/network. No test processes remain. No live migration, paid calls, index/source mutations, commits or deployment.
- R2.1 is complete. R2 as a whole remains in progress; R2.2 (atomic ledger and every-call accounting) is next, followed by R2.3 scheduler, R2.4 delivery APIs and R2.5/R2.6 recovery/acceptance. Schema fields alone do not implement leases, shared budgets or background execution.

### 2026-10-01 - R2.2 shared accounting implementation

- Re-read spec sections 7, 8, 10 and 11 and preserved the existing working tree. Application migration 4 adds partitioned protected holds, usage/document receipts and unique source-version accounting. Internal submission now initializes a validated versioned profile atomically with the objective; replay does not reset allowances or deadlines.
- Added `research/{budgets,ledger,accounting}.py`. Objective-locked reserve/start/settle/release operations reject stale leases, expired exploration, cancellation, duplicate dispatch and conflicting receipts. Concurrent reservations cannot spend the same capacity. Missing provider usage stays reserved; an overrun persists its receipt and blocks new work. Settled document counts deduplicate versions while repeated delivered rows/bytes still consume budget.
- Integrated trusted accounting around Supervisor/worker/review/final model attempts, retries, worker data calls, embeddings, MCP/document reads and each hybrid-search branch. Two provider attempts are charged separately; accounted retry failures cannot trigger another graph retry layer. Accounting transactions end before external I/O. Caller cancellation stops waiting but retains ownership of the underlying resource slot; late usage settles before stale/cancelled output is rejected.
- Worker budget stops use extended result stop reasons and existing LLM finalization. Root exploration exhaustion disables delegation and uses protected submission/review/repair/final capacity. Conservative worker holds serialize otherwise parallel independent work when only one allocation fits; D04/spec section 8 records the exact defaults. Ordinary streams retain their existing local behavior. Background invocation requires matching trusted accounting identity and cannot resume the legacy graph.
- Tests use manually provisioned synthetic leases and scripted providers against real isolated PostgreSQL. R2.3 still must implement fenced claims and bind one shared resource owner per API process. R2.5 must reconcile uncertain work across process death; this slice does not claim scheduler execution, provider exactly-once behavior, cancellation API or crash recovery. Research/Python and background HTTP remain disabled.
- Validation so far: initial full container suite 146 passed/4 hosted skipped. Added protected-root repair test initially failed because its scripted model supplied an empty answer package; corrected the fixture to return an explicit evidence limitation. Existing answer validation was retained. Final acceptance result follows below. No hosted calls, source/index changes or active-stack migrations.

### 2026-10-01 - R2.2 accepted

- Final isolated Linux/PostgreSQL run: **147 passed, 4 hosted skipped in 32.82s**, using `podman compose -p comtech-research-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests`, image `635113f9918ee5295d492f59cc2e00c21ed584c6f5388258f79eaec269d1cd14`. No runtime/test code changed after this build. Checks cover last-reservation races, partitioned holds and rollback, uncertain usage, immutable receipts, pinned document dedupe, stale/cancelled/deadline rejection, canonical graph identity, protected worker/root LLM finalization, review repair, retries, source fan-out and resource ownership after caller cancellation.
- Ruff check and format check passed for all changed Python modules/tests; `git diff --check` passed. Spec/defaults, operation docs and checkpoint updated. The isolated containers/network were removed; cached images remain. No deployment, active database migration or paid provider calls occurred.
- R2.2 is complete. R2.3 is next; background/research execution stays disabled. Preserve the ledger rather than reconstructing counters from checkpoint content, and bind shared resources once per owner rather than separately for each branch or run. Live provider accounting and hosted semantic evaluation are not covered by the scripted suite.

### 2026-10-01 - R2.3 internal queue and continuations (acceptance in progress)

- Read spec sections 7, 8, 10 and 11, the checkpoint/decisions and operation docs. Preserved existing work. Starting spec SHA256 `9A8D1547EBE7C63386E6EEBEBEF85C824024268A73C70717E2532E31AA9231AB`. No source story/private evaluation content or hosted services were inspected.
- Added migration 5 (`research/queue_schema.py`) with compact continuation/admission fields, dependency delivery and immutable per-attempt transitions. `TaskQueue` serializes claims and locks objectives in ledger order, creates fenced attempts, renews leases within the original deadline, enforces global/per-run admission and registers child allocation/creation in one transaction. Duplicate work keys cannot change their input/kind/allocation; duplicate transitions return the committed receipt without replaying mutations.
- Waiting parents release their task lease and become ready after a fresh terminal dependency. Failures/cancellations wake waiters too, and all-terminal dependencies cannot strand a parent. Dependency validation rejects foreign tasks, self/ancestor and cross-branch cycles. Ready continuations get priority over fresh work. Terminal task records are immutable; unresolved usage preserves its reservation/hold.
- Added supervised scheduler consumers and lifespan ownership inside the API's existing singleton lock. Each attempt binds shared accounting resources; heartbeat loss stops semantic work. Shutdown stops consumers and drains detached operations before API ownership/adapters close. The resource drain must include nested calls created during shutdown, not only the initial task snapshot. Production handler registration remains empty: this is internal scheduler acceptance, not HTTP or Research feature enablement.
- Tests cover concurrent claims/admission, budget rollback, early parent wakeup with a single execution slot, terminal failure/cancel outcomes, stale leases, cycles, immutable result commits, shared resources and heartbeat renewal. Added a PostgreSQL-backed LangGraph test that stores a checkpoint reference, releases the parent, and resumes under a new attempt without repeating the prior node; plus shutdown/nested-call and handler-failure tests.
- Initial checks: 51 offline tests passed/3 hosted skipped; full isolated Linux suite before final boundary additions: 153 passed/4 hosted skipped. Ruff and format checks passed. Final boundary checks are in progress. R2.4 must connect actual handlers/HTTP and atomically publish final answers; R2.5 must reconcile expired leases/uncertain external work; R5 owns semantic child admission, progress and unnecessary/shared-branch retirement. No expired lease is silently reclaimed in R2.3.

### 2026-10-01 - R2.3 accepted

- Final command: `podman compose -p comtech-research-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests`: **156 passed, 4 hosted skipped in 35.72s**. Image `8764e7d35840d0dcc7134cdadbbc086844a3d91aeae1c847429c916f4e34b15d`; runtime/test files unchanged after the final build. This includes the nested-call shutdown regression and atomic outer specialist/research-task charging.
- Ruff check/format check and `git diff --check` passed. Migration 5 and lease/continuation behavior ran only in isolated PostgreSQL. The test containers/network were removed; no active database migration, deployment, source/index modification or paid calls occurred. Spec, operation docs and this checkpoint reflect implemented versus enabled behavior.
- R2.3 is complete. R2.4 is next. Task completion currently persists an internal result only; it must not be mistaken for an atomically published reviewed user answer. Production handlers remain unregistered, and expired/uncertain work requires R2.5 reconciliation before retry. LangGraph checkpoint/queue crash-window acceptance belongs to R2.5/R2.6; the R2.3 test demonstrates a normal durable waiting continuation, not full crash recovery.

### 2026-10-01 - R2.4 implementation (acceptance in progress)

- User requested continuing all remaining phases in order, with validation/checkpoint updates at each step. R2.4 reads spec sections 7.4 and 10; R2.3 baseline remains 156 passing tests/4 hosted skips. D01 clarification requested asynchronously while independent R2 work continues.
- Added opt-in background submission (HTTP 202, explicit mode/idempotency key), bounded status/result views and replay-follow event connections that do not own execution. Default mock/legacy stream behavior remains unchanged; background requires enterprise mode and is disabled by default.
- Registered the ordinary reviewed graph under the singleton scheduler when enabled. Progress uses transactional event sequencing (migration 6). Root task completion, stored reviewed result, final message events and terminal status commit in one transaction; failures publish control errors without invented answers. Duplicate terminal commits reuse their immutable task transition. Added injected-storage-failure rollback and real HTTP/scripted-provider tests for duplicate submissions, disconnect/reconnect, review failure and replay after restarting the API.
- Background execution/HTTP is available only in the opt-in test configuration at this stage. Recovery, cancellation and ambiguous external completion remain R2.5/R2.6. R3-R6 are still pending; no hosted calls, source/index changes or deployment.
- D01 user response: "for research lets not add mcps yet." Explained the difference between existing bounded lookups and proposed complete collection queries/aggregates. New Research is document-only for this release; ordinary Knowledge Worker MCP remains available. Research broker lookup/collection capabilities must be unavailable rather than reading fixtures directly.

### 2026-10-01 - R2.4 accepted; R2.5 started

- Final isolated Linux/PostgreSQL suite: **163 passed, 4 hosted skipped in 47.18s**, image `3723a4f67704086c233b36c157f64388ae312f90a84d5cb66f0ea3e861ff8720`. Ruff passed. No runtime/test files changed after the image build. The isolated stack is stopped and retained for the next phase's tests; no live migration or hosted calls.
- Migration 6, `research/{background,delivery}.py`, queue terminal hook, opt-in settings and API submission/status/result/replay-follow routes implement R2.4. Legacy mode remains supported. Background flag defaults off and Research is not advertised. Cancellation/restart recovery now proceed under R2.5; full durable acceptance remains R2.6.


### 2026-10-01 - R2.5/R2.6 implementation and recovery checks

- Added persisted bounded call receipts before graph advancement; replay identity includes scope, role, payload, schema, provider attempt, selected model and prompt/tool definition. Recovery reconciles recorded output/cost receipts, retains unknown usage, and terminates ambiguous external attempts with `uncertain_external_completion` instead of guessing or retrying them. Restart preserves the canonical run, source pins, absolute deadline and cumulative budget.
- Added idempotent cancel, periodic expiry/accounting-failure termination, source-pin checks, graph checkpoint continuation and canonical background resume acknowledgement. Resume never creates another run; stale/unrelated/terminal checkpoints are rejected. Cancellation prevents new paid finalization and records late incurred costs. Existing stream resume behavior remains separate.
- Synthetic PostgreSQL tests cover cached calls, interrupted graph continuation, completed checkpoint publication, output persisted before cost settlement, unknown outcomes, cancelled/expired/version-mismatched runs and HTTP API shutdown immediately before final publication. The new HTTP test observed one answer and no repeated provider calls; its initial assertion incorrectly required protected holds to remain after completion. Corrected it to require unchanged ceilings/consumed/reserved usage and released unused holds.
- Final isolated rerun pending. No claim of provider exactly-once execution: a crash after dispatch but before a durable receipt remains uncertain and stops the run. No Research MCP capability was added; spec and plan record D01 throughout, including deferred SDK lookup/collection contracts.


### 2026-10-01 - R2.5/R2.6 accepted

- Final command: `podman compose -p comtech-research-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests`: **175 passed, 4 hosted skipped in 55.03s**. Image `a5257fe729757a1a1a857bb4d72c270796ef011da8cb191cf2c00234ae694a25`. No runtime/test edits after that build. Ruff lint/format and `git diff --check` passed. The previous 174-pass image also accepted the canonical resume endpoint; this final run adds the tool-receipt/checkpoint crash-window case.
- Verified interrupted worker continuation after a saved tool receipt, completed graph recovery, HTTP API shutdown before answer publication, output-before-cost reconciliation, claim/transition races, cancellation, stale/cross-run checkpoint rejection, changed pins and deadlines during downtime. Consumed usage never resets; completion releases unused protected holds. Repeated resume returns the same active run and does not invoke a second graph. Final answer publication remains singular and transactional.
- Recovery is conservative, not provider exactly-once delivery. Unknown dispatched outcomes fail without retry/refund; tests use injected interruption/storage failures and API lifespan restart with scripted providers, not hosted provider crashes. Broker capabilities, Python process containment and recursive Research recovery are still R3-R6 work.
- R2 complete. Research remains unavailable and background defaults off. D01 remains document-only Research with existing ordinary MCP tools preserved. Next dependency-ready work: R3.1. No active-stack changes, hosted charges, source/index changes or deployment.


### 2026-10-01 - R3 tool audit and D05 clarification

- Inspected KnowledgeTools, SearchArgs/ReadArgs, SourceStore, HybridSearch, runtime wiring and synthetic retrieval tests. Existing document tools already provide the desired bounded search and expansion shapes; MCP remains a separate tool set. No runtime files changed in this slice.
- User clarified that Research needs recursive discovery, restricted Python execution, and direct search/expansion. The former spec included the first two but limited Research data tools to Python. Updated sections 1, 2, 5.2, 6.1 and acceptance criteria, plus R3.2/R5.1 tasks, to add direct shared retrieval for parents and children. Python restrictions and optional early completion remain unchanged; D01 still defers Research MCP.
- Direct calls and Python SDK calls must share underlying retrieval and argument/result contracts, while enforcing their respective trusted call/execution identity, inherited scope, pins, provenance and cumulative accounting. No Python execution is needed for a direct read or child proposal.
- Documentation changes only; previous 175-pass/4-hosted-skipped runtime validation remains the baseline. Next: implement R3.1 contracts/capabilities with both direct-call and Python-execution bindings, then R3.2 shared document tools. The earlier direct-versus-Python clarification is resolved by the user's explicit direction; no further confirmation is needed.


### 2026-10-01 - R3 implementation; acceptance in progress

- Added migration 7 for immutable document task scopes, expiring hashed capabilities bound to fenced attempts and optional Python executions, durable scoped data references/explicit inheritance, opaque query-bound cursors and immutable request identities. The public SDK contains no management, provider or MCP methods.
- Shared Knowledge Worker document dispatch in `retrieval/tools.py`; reused exact SearchArgs/ReadArgs and result shapes. HybridSearch intersects trusted document IDs into both query branches and uses a fixed query-embedding port; ordinary worker MCP is unchanged. Research direct tools require no Python execution.
- Added published-metadata enumeration, explicit version-family policy, effective-date exclusions, exact character paging, scope/pin checks and coverage distinct from semantic interpretation. JSON/Parquet artifacts store input/code/environment lineage, hashes, explicit grant inheritance, bounded pages and active-run-aware retention. R4 still owns runner/transport integration; R5 owns exposing Research to Supervisor and reviewed computed claims.
- Synthetic tests use the existing generated release fixture, scripted Pinecone/embedding responses and real isolated PostgreSQL. Initial Windows pytest had temporary-directory permission setup failures, including workspace temp directories; rerunning with ordinary Windows permissions. Isolated Linux suite building/running under `comtech-research-tests`; no live source/model calls. Ruff passes. No R3 task marked accepted yet.
- Research extra pins already-locked PyArrow 25.0.1; only the isolated test target installs it at this stage. SDK transport is injected; no runner network boundary is claimed by these broker tests. Source credentials remain in trusted adapters, and the fixed embedding operation accepts only query text for the pinned model/dimensions.


### 2026-10-01 - R3 boundary checks

- Expanded isolated Linux/PostgreSQL suite: **189 passed, 4 hosted skipped in 59.37s**, image `add985161765deb21fc9ffcbabc0d6ea9a419e1050556785aa61342c887e9ac7`. `uv lock --check --offline` passed inside that image (124 resolved packages); this checks the research extra against the existing lock rather than relying only on frozen installation.
- Added a post-registration document-result bound so durable evidence IDs/rankings count toward the same shared token limit; returned expansion counts are recomputed and omitted sections remain explicit. Added artifact expiry and orphan-write cleanup tests, including preservation of active and unmanaged files. That image passed **190 tests, 4 hosted skipped in 57.64s**, image `33df8932e036133d0157ec5f397f9eb2c514fd13c066f7bc445d39acd75119dc`.
- Final addition requires the scope to allow metadata returned with an observation (title/effective dates), not only content; a synthetic child-scope test rejects the request before source or embedding calls. Final complete image validation pending. Ruff check and format check pass. Removed only this session's failed pytest temporary directory after verifying its workspace path.
- Spec sections 6.1-6.5 and operation docs now distinguish implemented document enumeration/counts from deferred MCP QuerySpec/lookup operations, use existing SourceScope version-policy literals, and record broker/SDK/retention boundaries. Python isolation/transport, recursive reasoning and final application wiring remain R4-R6. No hosted calls or active-stack changes.


### 2026-10-01 - R3 accepted

- Final command: `podman compose -p comtech-research-tests -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests`: **191 passed, 4 hosted skipped in 58.64s**. Image `1f49e19bd70d8a5c7d2645b3ababb5fc753a83819eeff551982dd9ef7d5f2671`. No runtime/test files changed after this build. Ruff lint/format, dependency lock validation and `git diff --check` passed. Final spec SHA256 is recorded in the checkpoint.
- Accepted R3.1-R3.4/R3.6: shared direct/Python document contracts; immutable narrowed capabilities and source pins; field/metadata restrictions; pre/post accounting with source fan-out and replay; exact spans and query-bound cursors; metadata enumeration versus semantic coverage; JSON/Parquet lineage, grant inheritance, expiry/hash failures and active-run-aware retention/orphan cleanup. These checks use generated test documents, scripted provider responses and real isolated PostgreSQL, not live banking story sources or hosted models.
- R3.5 remains deferred under D01. Research does not broker existing or new MCP tools, and ordinary Knowledge Worker MCP remains unchanged. The broker has no general collection QuerySpec or raw Pinecone/SQL interface; Pinecone search uses the shared bounded search tool.
- R4 must wire the SDK and fixed embedding port through the selected restricted service transport and verify actual Python/network/process isolation. R5 must implement recursive semantic decisions and connect durable evidence/computation records to selected claims. R6 must integrate UI, lifecycle, final retention selection/maintenance and end-to-end acceptance. These boundaries are not implied complete by R3 tests. Research remains unavailable and background defaults off.
- Removed the isolated test containers/network after successful completion. Cached images remain. No active database migration, source/index modification, paid calls or deployment. Next: R4 host/runtime feasibility and R4.1.


### 2026-10-01 - R4 started; D02 feasibility

- Read R4 technical sections and checkpoint; preserved existing changes. Target is Podman 5.8.2/crun 1.27, Linux 6.6.114.1 WSL2, cgroup v2 with memory/pids/cpu controllers and seccomp. Docker engine is not installed; Docker acceptance must remain explicitly unverified.
- Disposable network-none/read-only/non-root container with only SETUID/SETGID/KILL supervisor capabilities successfully changes to UID/GID 10001. Probe found capabilities survive that change, so the trusted bootstrap explicitly clears permitted/effective/inheritable/ambient capabilities before generated code. Verified zero capability sets, no_new_privs, a third seccomp filter, denied socket creation/fork/UID escalation and a successful ordinary calculation.
- D02 selects protected Unix control transport instead of a network-accessible runner. Generated code gets an inherited data channel; the supervisor relays bounded requests over the already-authorized client connection. Execution capability stays in the trusted broker client, never in generated code. Runtime permits one numerical thread and forbids generated process/thread creation via seccomp; no descendant can escape via setsid/fork. Full image, cancellation, resource and SDK tests remain R4 work. No hosted calls or active-stack changes.


### 2026-10-01 - R4 implementation and boundary corrections

- Added the minimal runner image, protected Unix control protocol, dedicated generated-code UID, explicit capability clearing, stacked seccomp, Landlock workspace restrictions and CPU/address-space/task/file/output limits. The SDK channel carries only bounded data operations; capabilities remain in the trusted client. Numerical libraries use the existing lockfile versions and no provider/application dependencies enter the runner image.
- Initial Compose tmpfs options required quoting as one YAML scalar. Podman also created the control volume root-owned; added an explicit one-time initializer with only CHOWN/FOWNER against that isolated volume. The runner remains non-root and fails closed on wrong ownership rather than relaxing control-directory permissions.
- Bootstrap initially rejected numerical-library helper threads. Moved kernel enforcement before library imports, allowed only same-process clone threads with inherited restrictions, and retained the 16-task ceiling. The complete initial run had 9 failures/191 passes/4 skips and one setup error; it was not accepted. Fixed cancellation precedence so revoked capabilities still report a cancelled run consistently with R3. Focused rerun then had 26 passes, one skipped restart and one fixture failure: read-only writes return EROFS, not always PermissionError. The fixture now accepts only EPERM/EACCES/EROFS for denial.
- PythonExecutor persists code/input/purpose/scope/environment identity, registers fenced execution capabilities, applies the shared ledger to Python and nested SDK calls, separates capped logs from model output, and replays committed results without rerunning. Client disconnect/cancel/deadline closes control and stops the process. An interrupted container produces an immutable failed request; uncertain API crash windows retain R2's conservative accounting. Retention hooks expire logs/code while preserving active evidence and manifests; R6 scheduling is pending.

### 2026-10-01 - R4 accepted on the local Podman target

- Runner image: `f61fb4a1ca6c5964916951980c336e645f7df9968e0bb3b436d271e65ed0b038`. Inspected actual configuration: read-only root, network `none`, memory 2147483648 bytes, 64 PIDs, CPU quota/period 200000/100000. Runtime is Podman 5.8.2/crun 1.27, Linux 6.6.114.1 WSL2, cgroup v2, Landlock ABI 3. Docker engine is absent and remains unverified.
- Final full command: `podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml run --rm --no-deps tests uv run --frozen --no-sync pytest -q -p no:cacheprovider`: **206 passed, 5 skipped in 86.83s**. Four skips are hosted checks; the fifth is the separately orchestrated restart case. The test client uses read-only current source/test mounts; the runner uses its built minimal image with no repository/source-store mount. No runtime code changed after the accepted full run.
- Separate restart command adds `-e RUN_RUNNER_RESTART_TEST=1` and selects `tests/research/test_runner.py::test_container_restart_during_execution -q -s -p no:cacheprovider`. On `RESTART_READY`, ran `podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml restart python-runner`: **1 passed in 19.49s**. Interrupted request stayed failed on replay with unchanged usage; a new job saw a clean temporary filesystem. API logical recovery also reused a committed execution under a new fenced attempt without new usage.
- Added explicit IPv6, native x86_64 socket-syscall and escaped-session attempts to the already passing boundary case; its focused final rerun passed **1 test in 2.59s**. The suite also covers brokered search/read/calculation, Parquet continuation via pandas, PyArrow threaded aggregation, inherited thread restrictions/task exhaustion, wall/CPU/memory/output/file/tmpfs limits, forged broker requests, source/runner outage, control disconnect, explicit cancel, hostile workspace permissions and log/code retention. The fixture's synthetic diagnostics are not public answer events.
- `uv lock --check --offline` passed (124 packages); Ruff lint/format and `git diff --check` passed. Initializer and shutdown commands are recorded in docs/agents.md. Removed only the isolated test stack/network/control volume; cached images remain. No hosted charges, active database migrations, source/index changes or deployment.
- R4.1-R4.5 complete for this target. R5.1 is next. Research is still unadvertised; R5 must implement the semantic loop/recursive admission and reviewed result export. R6 must package the trusted broker/client and fixed embedding transport, UI/lifecycle/readiness and scheduled retention. The tested same-kernel container boundary is not production hostile-tenant certification; unsupported runtimes must remain disabled.

```text
Date and executor:
Task IDs and outcome: completed / in progress / deferred / blocked
Spec revision or hash and sections consulted:
Code revision and relevant uncommitted changes:
What changed and why; implemented / validated / enabled state:
Files and contract/migration versions affected:
Checks: exact command, environment, passed/failed/skipped result
Decisions or deviations: decision ID, rationale, spec updates
Remaining work or failing case:
Running jobs/containers or external side effects to account for:
Next task and exact next action:
```

### 2026-10-01 - R5 implementation and acceptance

- Read the R5 technical sections, queue/ledger, R1 evidence/review adapter and accepted R3/R4
  interfaces. Added versioned Research actions/prompts, a checkpointed task loop, atomic recursive
  admission, scope/input grants, dedupe/cycle guards and early completion. Direct search/read uses
  Knowledge Worker's shapes; Python and child delegation are independent additional actions.
- Local pre/post context checks and cumulative ledger admission preserve tool-free LLM finalization.
  Two consecutive steps without new span/computation evidence stop exploration. A task reserves two
  full local context allowances for its finalizer/provider retry within the one run ledger. Child
  admission does not multiply the objective budget, and batch failure rolls back task counts/holds.
- Completed children export only selected claim/premise/source/computation closures. Durable broker
  records hydrate the R1 validation boundary; source owners are preserved. Shared dependencies protect
  still-needed branches, retired attempts cannot publish late results, and late usage settles before
  releasing their unused holds. Recovery reuses committed model/tool receipts and graph checkpoints.
- Added an opt-in Research specialist dependency to the Supervisor graph and background continuation
  handler. Waiting releases the parent slot; approved output still passes through package validation,
  at most two reviews and final-only publication. Repair may request another Research root under the
  same objective. Default application/runtime wiring is unchanged and remains an R6 responsibility.
- Native Research calls use locally validated schemas, with exact shared search/read arguments.
  Scope-map proposals use non-strict provider function schemas and strict local Pydantic/broker
  validation; no provider-side schema guarantee is claimed for them. Research uses the configured
  complex-worker model with medium effort. Implementation reference:
  [OpenAI structured outputs and function calling](https://developers.openai.com/api/docs/guides/structured-outputs).
- Python manifests and analysis artifacts include trusted prompt/model/step/mode identity, execution
  times and selected source lineage. Mixed-analysis fixtures preserve unknown classifications and
  event identity dedupe; counts remain explicitly limited to those classifications. These scripted
  fixtures establish control/provenance and known calculations, not hosted semantic accuracy.
- Acceptance found and corrected final-model context leakage, the native shared-search argument
  adapter and a misplaced provenance keyword. The synthetic expired-deadline fixture was adjusted
  to preserve the database's creation/exploration/final deadline ordering. Final acceptance is
  recorded in the current checkpoint/phase status: 226 passed/5 skipped in the complete suite;
  27 passed in the final focused Research/model suite. Ruff lint/format and whitespace checks pass.
  No source/runtime changes followed that focused pass. Isolated acceptance services were removed.
- No new migration beyond migration 7, source/index modification, hosted call, application enablement
  or deployment. R6 must package trusted service/embedding transport and readiness, connect API/UI,
  schedule retention, and evaluate live-provider behavior separately.

### 2026-10-02 - R6 local integration acceptance; hosted evaluation pending

- Read specification sections 10-14 and the R6 plan/checkpoint. Preserved existing staged and
  unstaged work. Added opt-in Research application wiring, leaving mock/stream defaults and
  Knowledge Worker's seven MCP tools intact. Research remains document-only under D01.
- R6.1: background UI uses a stable submission key, persisted conversation/run/cursor, finite
  replay polling, explicit cancellation and stored reviewed answers. Streamlit AppTest verifies
  reload without resubmission; the client test verifies ambiguous acknowledgement retry and that
  event text cannot bypass the final-result gate.
- R6.2: migration 8 and scheduled maintenance implement explicit result expiry and selected
  evidence retention. Status/activity expose bounded identity, mode, usage and selected coverage
  metadata. Research trace input/output is redacted. API cases passed with an unavailable Phoenix
  exporter as well as tracing off. Fixed development retention durations and separately retained
  conversation/audit history are now explicit in spec 11.3 and operation docs.
- R6.3: private API/broker HTTP requires service authentication and current fenced leases.
  Source pins/read limits/runner digest are checked at readiness. The API owns a fixed embedding
  operation; broker owns sources/artifacts/runner control and rejects model credentials. Added
  minimal broker modules to its image, opt-in `compose.research.yaml`, separate source/artifact/control
  mounts, and a synthetic readiness overlay. No broker/runner host ports or generated-code model/MCP
  access. Built broker image `b4eecde5a549ca2a615d9b2e490e476892835165609f274d1223648ed71fc762`
  returned ready with the synthetic release and runner digest
  `70807d23ac905a9ea3c85bd821eec503e8d8c9f7b98fdd8cadefbca3292ec3ee`, including after runner restart.
- R6.4: actual HTTP API/broker, PostgreSQL, queue/checkpoints and restricted runner passed ordinary,
  semantic, deterministic and mixed routes; duplicate submit, final-only replay, recursive children,
  early fact completion, source outage/partial answer, cancellation during Python, source-contract
  readiness failure, expiry and API recovery after a saved Research result but before queue commit.
  Recovery did not repeat settled Research model/embedding calls. Existing budget/scope/concurrency/
  lineage/isolation and review-repair regressions remain green.
- Full command: `podman compose -p comtech-runner-tests -f compose.test.yaml -f compose.runner-test.yaml
  run --rm --no-deps tests uv run --frozen --no-sync pytest -q -p no:cacheprovider`:
  **246 passed, 9 skipped in 145.12s**. Test image `ea9583b7446dfed88c932e5303544c730ed94391673095cb63d82bf771252dd4`
  with read-only current src/tests/ui mounts. Eight hosted checks were skipped. The ninth skip was
  separately exercised with `RUN_RUNNER_RESTART_TEST=1` and an isolated `restart python-runner` after
  `RESTART_READY`: **1 passed in 21.49s**. Ruff lint, 120-file format check and diff whitespace passed.
  Only formatting/docs and a hosted prompt line wrap followed the full test run.
- The first UI harness invocation used a relative Streamlit entrypoint resolved under tests; fixed
  it to an absolute path. The fixture initializer initially used system Python; fixed it to the
  test virtual environment. Both fixes passed their reruns. No unresolved local acceptance failure.
- R6.5: four opt-in hosted cases and JSON quality reports are prepared in
  `tests/research/test_hosted_application.py`; operation/configuration/handoff docs updated. No
  hosted Research calls have been made. Explicit approval requested for this new paid/content
  transmission scope; prior approval covered the original four enterprise smoke tests. Semantic
  support, classification uncertainty, coverage and useful stopping require review of actual results.
  R6 is not fully closed until that evaluation is completed or explicitly deferred.
- Tests changed only the isolated project. No active deployment, active database migration, source
  mutation or Pinecone writes. Acceptance containers/network/private test volumes are removed at
  handoff; cached images remain. Docker and remote/Railway support remain unverified.

### 2026-10-02 - Complex evaluation catalogue and offline harness

- The user authorized proceeding with R6.5, then requested nearly 30 complex test cases. Created
  30 scenarios / 33 turns: eight Knowledge Worker, six semantic, five deterministic, five mixed,
  three cross-worker and three limitations/adversarial cases. Used published catalog identifiers
  and tool contracts; no private canonical truth or hidden evaluation answers were read.
- Added `tests/research/complex_cases.json`, a separately gated hosted runner and local HTTP harness.
  Per-case rubrics cover entailment, dates/authority, coverage, arithmetic, uncertainty and useful
  stopping. Follow-ups preserve thread identity. Reports retain failed results and pending semantic
  review; failure cleanup discovers ambiguous submissions and requests cancellation in that case's
  fresh thread. Automated success never marks semantic review passed.
- Offline harness verification in the network-disabled cached Linux test image: eight passed,
  30 hosted cases skipped. Windows collection found all 30 cases; lint/format passed. Windows
  temporary-directory permission errors prevented filesystem fixtures, so container verification
  was used instead. The published identifiers were checked without reading hidden answer material.
- No application/runtime changes, deployment, migrations, provider calls or source/index writes.
  The disposable test container was removed. Hosted evaluation remains pending; neither R6.5 nor
  the new scenarios are claimed accepted against live models. See `docs/research-evaluation.md`.

### 2026-10-02 - 30-case live baseline completed; acceptance failed

- User explicitly requested executing all 30 complex cases and starting required services. Built
  and started the isolated `comtech-complex-eval` API/UI/PostgreSQL/MCP/broker/runner stack with
  a private generated environment, separate volumes and localhost ports 18000/18501. Host-side
  Podman configuration required sandbox escalation; automatic review allowed it. Runner retained
  the previously accepted image/boundary. No production stack or provider index was changed.
- Exact command and image/source fingerprints are in `docs/research-evaluation-results-2026-10-02.md`
  and ignored local artifacts. The model configuration and app build remained fixed. No application
  repair or paid rerun was mixed into the baseline. Result: **27 failed, 3 passed in 1608.03s**.
  Submitted 31 turns; KW08 stopped before its two follow-ups. EDGE29's clarification passed and its
  second turn failed. Four runs completed, 27 failed, and no runs/tasks remain active.
- Codex source-evidence review accepted KW06, RS13 and EDGE28 against their authored criteria;
  this is not independent human sign-off. Matched all 17 selected document spans/hashes to the
  published source store. RS13 stopped after one search/read without recursion/Python/enumeration.
  EDGE28 preserved unavailable financial data but was inefficient and overlong. Other case-level
  semantic criteria remain unverified; no failed scenario was called an answer-quality pass.
- Checkpoint audit identified 15 reference-admission failures, three missing-evidence failures,
  two malformed decision outputs, two citation-rendering violations and one each for missing
  derived premises, review exhaustion, omitted final claims, incomplete child scope and conflicting
  parallel requests. Numerical/mixed answers and live recursion are not accepted. No registered
  artifact values were produced; stopped enumeration needs further diagnosis.
- Ledger recorded 275 model requests / 1,193,747 model tokens, 53 embedding requests / 800 tokens,
  and 13 Python attempts. 21,039 model tokens remain conservatively reserved without recorded
  usage; protected capacity is not a charge. These figures are not a provider bill.
- Evaluation services remain healthy/running for inspection with retained volumes. Per-case JSON,
  JUnit, read-only database/execution/checkpoint export, independent metadata calculations and
  review notes are under `var/research-evaluation`. The original four-case smoke suite remains
  unrun. R6.5 stays unchecked: next work is remediation followed by regression/live acceptance.

### 2026-10-02/03 - R6.5 remediation and focused reruns

- Separated Research document selectors from registered inputs and added bounded admission/model
  feedback, durable rejected-call replay and two-attempt final wording. Fixed correction-only
  streaming updates after the first live subset exposed a KeyError. Source/evidence/review guards
  remain enforced; unknown incurred usage stays reserved.
- Bounded enumeration reservations by the pinned source population, allowing a 132-document
  release to satisfy a 1000-row request without reserving 1000 discoveries. Preserved validated
  MCP query parameters in hashed observations so empty results retain their query scope.
- Diagnosed PyArrow timeout with the full app running: generated code shared UID 10001 with
  API/UI/MCP and exhausted the UID-wide 16-task limit. Generated code/cleanup now use 10002;
  restrictions and limits remain unchanged. Runner tests changed from 37 passed/1 failed/1 skipped
  to 38 passed/1 skipped. Old image remains recorded in the original baseline.
- Revised unused-hold release after live KW04 lost its second lookup: completed scopes now close
  unused finalization capacity while unknown call costs retain their full reservations. Late
  settlement cannot restore a closed hold. In-flight/undispatched operations still block release.
- Final combined suite with PostgreSQL and actual runner: 198 passed/38 skipped in 116.42s;
  lint/format passed. The original baseline is preserved. Focused live checks remain insufficient
  for acceptance; detailed results and exact remaining work are in
  [the remediation report](../research-remediation-2026-10-02.md). All nine live attempts failed
  across three fixed builds; no hosted semantic passes. Last KW04 failed derived premises and
  RS13 exhausted review. Stack is retained with zero active jobs/tasks; R6.5 stays open.

### 2026-10-03 - Shared evidence and publication fixes

- Preserved all numerical token limits at the user's request. Added optional executed-process
  summaries and input coverage to calculation artifacts/reviewer input; provenance remains required.
- Worker and Research corrections now receive the rejected draft and claim-specific defects.
  Metadata handles remain durable without bloating prompts, and enumeration coverage counts as progress.
- Corrected the renderer's `EV-` substring test, which falsely rejected `SEV-1`/`SEV-2` in both
  baseline incident cases. Corrected the earlier attribution to invented citations in baseline docs.
- Final local regression: 207 passed/38 skipped with PostgreSQL and real runner. Focused live RD15
  produced a retained calculation artifact whose 132-version category totals match an independent
  metadata calculation. Method prose still overstated one check; details are in the remediation report.
- Final build: KW04, KW05 and RS13 completed. Source/trace review accepts KW04/KW05, but RS13 did not
  stop when supported and made two invalid section-read requests. Token efficiency remains poor.
  Final answers and evidence were inspected, not just automated status. No general acceptance claimed;
  R6.5 remains open. All reports/audits are retained separately from the baseline and nine earlier failures.

### 2026-10-03 - Shared contract, scope and recovery remediation

- Matched advertised reader schemas/defaults to configured limits and added bounded exact section
  navigation. Preserved original user intent for Research/Reviewer; clarified SDK result nesting,
  scoped version policy and truthful computation checks. Resolve exact document shorthand before
  scope checks, rejecting unknown selectors without empty-population research.
- Preserve trusted Python error feedback and successful source receipts after failures/oversized
  output; exclude failed artifacts. Remove duplicate evidence from model-facing envelopes and raw
  evidence from final wording while retaining complete runtime validation/citation state.
- Added bounded recovery for rejected child budgets, incomplete Supervisor submissions, failed
  specialist follow-ups and malformed new/inherited claim IDs. Failed drafts cannot contribute
  claims/evidence, exploration stays closed during correction, and all numerical limits remain.
- Final regression slices: 77 passed/1 skipped, then 29 Research +31 model/Supervisor passes and
  2 targeted checks, then 40 Research/registry passes. Ruff/format/whitespace checks passed.
  Counts overlap and are not a combined full-suite total. Details and prior failures are in the
  [remediation report](../research-remediation-2026-10-02.md).
- Twelve hosted turns across fix6-fix11 exposed and verified these paths. Final RS14 passed with
  one root/two successful Python batches, first-review approval and 32 source-verified inspected
  sections. RD15's latest focused run used one root/one Python execution with reconciled 132-version
  counts and real recorded checks. All six targeted case IDs have source-reviewed passes across
  successive builds; no single-build six-case or full 30-case acceptance is inferred.
- Token efficiency, irrelevant reads and citation verbosity remain open, alongside broader hosted
  acceptance. R6.5 remains open; exact images and next checks are in the checkpoint. Source pins,
  token limits, original baseline and earlier failed reports are preserved.

### 2026-10-04 - Full rerun and measured prompt/citation reductions

- Ran all 30 cases against unchanged fix11: 7 passed/23 failed in 877.16s; KW08 completed all
  three turns. Verified 25 document spans/hashes and 16 operational records. KW02/KW06 exposed
  misleading missing-evidence feedback for empty derived-claim citation selections. Later cases
  failed model retries; a minimal probe confirmed exhausted provider API credits. Stopped hosted
  calls; the 21 later failures do not establish semantic quality. See the remediation report.
- Added model-only audit/schema deduplication with matching input-size accounting and versioned
  replay identity. Grouped source citations preserve versions, snapshots and every exact locator;
  operational queries with different content/filter scope remain separate. Computed citations
  preserve execution/result/hash/coverage and durable full input lineage.
- Added claim-specific package feedback and one structural correction before semantic review,
  without new retrieval or weakening citation validation. Provider quota exhaustion is now
  non-retryable; the hosted catalogue stops later submissions on this explicit error.
- Same saved RS14 answer: evidence payload 12,346 to 7,879 tokens; citation entries 32 to 8;
  answer characters 6,110 to 4,477. These are deterministic input/presentation measurements,
  not measured end-to-end savings. Full batch recorded 673,929 model tokens (93% input), plus
  366,318 reserved with unknown usage, which is not a confirmed provider bill.
- Final regression: 159 passed/4 skipped with isolated PostgreSQL and actual Python runner;
  lint/format/whitespace pass. Optimized images deployed to the retained local evaluation app;
  startup readiness passed. Source data, all numerical limits and prior reports preserved.
- R6.5 stays open. Optimized-build hosted checks require restored credits; the fresh rerun script,
  exact image IDs, report paths and next actions are in the current checkpoint.

### 2026-10-04 - Full optimized-build rerun after credit restoration

- Executed all 30 cases/all 33 turns against frozen optimized images: 22 automated passes/8 failures
  in 3,579.98s. No quota interruption. KW06, all KW08 turns, EDGE29 clarification/follow-up and EDGE30
  completed. Preserved reports separately in `complex-2026-10-04-optimized-full`.
- Verified 160 exact document observations/hashes and 24 operational records against published/frozen
  sources. Independently checked numerical artifacts, including correct calculations in failed
  RD16/RD17/RD18 runs. Source inspection found RS12 used publication date as incident date despite
  automated completion; no claim of 22 semantically flawless answers or human sign-off.
- Diagnosed shared reference/lineage failures: KW02/XW25 invalid IDs; RD16 wrong citation namespaces;
  RM22 package/render ownership mismatch; RM23 explicit reference grants not recognized at export;
  RD18 JSON list versus tuple comparison rejects unchanged partial-span evidence. RD17/RD18 also
  lose usable calculation context under output/context bounds; RM24 spends recovery on retrieval
  without required arithmetic. Detailed scenarios and priorities are in the remediation report.
- Recorded 3,070,324 model tokens (2,842,327 input / 227,997 output), plus 220,446 conservatively reserved
  with unknown usage. Nine matched successful turns declined 3.34%; this is a single-run comparison,
  not isolated proof of optimization savings. Mixed-answer citation verbosity remains.
- No runtime changes during rerun; previous local regression remains 159 passes/4 skips. Final images
  unchanged, readiness 200, zero active jobs/tasks, retained localhost app on 18000/18501. R6.5 stays open.

### 2026-10-04 - Reference/citation contract remediation

- Added typed citation selections and one resolver used before review and during final rendering.
  Computations resolve through an authorized contributor; explicit reference grants are honored
  without changing provenance or expanding them to unrelated task-owned records.
- Fixed JSON/Python partial-span equality, introduced model-facing short reference handles and
  constrained final/worker selection schemas, supplied valid worker premises to review, and retained
  compact computation manifests during context reduction.
- Added approved-statement fallback after bounded wording failures and isolated ordinary-worker
  attribution failures so independent validated results survive. Integrity errors remain blocking.
- Token limits and existing evaluation stack images remain unchanged. Regression evidence is in
  `var/research-evaluation/citation-contract-2026-10-04/`; details and acceptance limitations are in
  `docs/research-remediation-2026-10-02.md`. R6.5 remains open pending another hosted acceptance run.
- Final full local regression with isolated PostgreSQL and Python runner: **333 passed, 1 skipped,
  38 hosted tests deselected**; Ruff and whitespace checks passed. The remaining skip requires a
  host-orchestrated runner restart. No paid model calls or evaluation-stack rebuild occurred.

## Resume instruction for a future executor

```text
Continue the recursive research implementation using
 docs/plans/recursive-research-implementation.md.
Read its current execution checkpoint, decisions and latest log first.
Read recursive_research_agent_implementation_spec.md and the active phase's
required sections; inspect current code/status and preserve existing changes.
Implement the next dependency-ready task, run its applicable checks, and update
checkboxes, phase status, the execution checkpoint and log with concrete evidence.
Research stops when the requested answer is supported; do not add unnecessary
corpus scans or child work. Do not reset budgets/state on recovery or bypass review.
```

[S1]: ../../recursive_research_agent_implementation_spec.md#1-decisions-and-relationship-to-existing-work
[S2]: ../../recursive_research_agent_implementation_spec.md#2-routing-and-role-boundaries
[S3]: ../../recursive_research_agent_implementation_spec.md#3-actual-sources-and-knowledge-domains
[S4]: ../../recursive_research_agent_implementation_spec.md#4-components-and-trust-boundary
[S5]: ../../recursive_research_agent_implementation_spec.md#5-contracts-and-evidence-compatibility
[S6]: ../../recursive_research_agent_implementation_spec.md#6-research-data-broker-and-coverage
[S7]: ../../recursive_research_agent_implementation_spec.md#7-recursive-scheduling-state-and-deduplication
[S8]: ../../recursive_research_agent_implementation_spec.md#8-budgets-and-deterministic-stopping
[S9]: ../../recursive_research_agent_implementation_spec.md#9-python-runner-and-artifacts
[S10]: ../../recursive_research_agent_implementation_spec.md#10-background-application-lifecycle-and-delivery
[S11]: ../../recursive_research_agent_implementation_spec.md#11-failure-audit-and-retention-behavior
[S12]: ../../recursive_research_agent_implementation_spec.md#12-deployment-and-repository-mapping
[S13]: ../../recursive_research_agent_implementation_spec.md#13-implementation-phases-and-acceptance
[S14]: ../../recursive_research_agent_implementation_spec.md#14-worked-flows-and-remaining-decisions
