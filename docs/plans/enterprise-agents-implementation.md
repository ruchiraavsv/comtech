# Enterprise agents: phased implementation tasks

Status: all four phases implemented and validated. Authorization remains deferred.
Date: 2026-09-29.

Implement the four roles from `enterprise_agent_architecture_v1_3.docx`:
Supervisor, Knowledge Worker, Reviewer, and Final Answer Generator. Use the
existing application, LangGraph/checkpointer, ingestion handoff, and seven-tool
Northstar MCP service. The [alignment review](enterprise-agents-alignment.md)
records the source inventory and architecture differences.

This plan incorporates the user's document expansion and worker budget design.
Implementation was subsequently authorized and preserves the existing MCP server contract.

## Scope and fixed decisions

- Authorization is explicitly deferred: no authentication, RBAC, scope checks,
  field redaction, or authorization acceptance tests in these phases. Preserve
  existing access metadata for later work; it does not enforce access today.
- Work with the synthetic data in a trusted development context. Per-task,
  per-run, and per-thread state correctness remains in scope; authenticated
  ownership and cross-user access enforcement are deferred.
- Collection-wide enumeration, aggregate rankings, Python analysis, extra MCP
  endpoints, and the complete golden evaluation suite are deferred.
- Use one Knowledge Worker implementation for both source families. Workers do
  not create sub-agents. Supervisor delegates objectives, not individual calls.
- Documents provide historical explanations, decisions, effective policies, and
  procedures. MCP provides operational state at `2026-09-15T10:00:00Z`, snapshot
  `DEMO-2026-09-15-A`. Never substitute the machine clock or historical documents
  for unavailable current records.
- Use native graph state, reducers, subgraphs, routing, retries, checkpointers,
  and streaming. Do not introduce a separate agent message bus, evidence database,
  or duplicate business-state event history.
- Generated source prose is data, not executable instruction. Canonical authoring
  files and hidden expected answers stay outside the worker's source adapters.
- These are four graph roles, not four deployed services. Start sequentially;
  add parallel independent worker objectives in Phase 4.

## Phase map

| Phase | Deliverable | Depends on | Exit check |
| --- | --- | --- | --- |
| 1 | Contracts and source adapters | Existing MCP and published ingestion artifacts | Search, bounded reads, and all seven MCP calls return attributable observations |
| 2 | Bounded Knowledge Worker | Phase 1 | One objective produces validated claims or explicit unresolved information within enforced budgets |
| 3 | Four-role graph, sequential workers | Phase 2 | Reviewed, cited answers for document-only, MCP-only, and mixed-source requests |
| 4 | Application integration, follow-ups, parallel workers | Phase 3 | API/UI conversations, checkpoint recovery, and concurrent objectives preserve evidence and control boundaries |

Each phase ends with its acceptance checks and a short implementation/validation
record. Finish a working phase before expanding to the next. IDs below are stable
task references, not separate agents or an instruction to delegate implementation.

## Required worker contracts

### Document discovery and expansion

`knowledge_search()` finds candidate documents. It may return bounded snippets,
scores, versions, and section references, but does not automatically promote hits
to evidence. Retain the architecture's document-type, department, service, date,
and bounded top-k filters. Temporal filtering follows the question; do not
globally remove superseded versions needed for historical comparisons.

```python
read_document_sections(
    document_id: str,
    query: str,
    section_ids: list[str] | None = None,
    max_sections: int = 3,
) -> ReadDocumentSectionsResult
```

The query is required and nonblank. Resolve `document_id` within a pinned release
to an exact document version. Without `section_ids`, rank sections within that
document using the query. With IDs, read only those sections after validating
their document/version membership; the query can locate a bounded excerpt inside
an oversized section. Reject invalid IDs, empty explicit lists, and requests over
the configured section count with structured errors; do not silently read a
different document or return arbitrary sections.

Return a typed result containing:

- Document ID/version and stable observation IDs.
- Sections with heading, section ID, exact source reference, returned source
  spans, text, content hash, and measured token count.
- Per-section `is_partial` and bounded continuation information, such as remaining
  span locators, so a later narrower query can inspect another part.
- Result-level token count, truncation/coverage information, and any structured
  errors. Coverage describes what was returned, not everything the document says.

Rank through the existing section/passage index and metadata; materialize exact
source spans from the source store. For an oversized section, return query-relevant
contiguous excerpts with exact offsets, not an LLM summary labeled as source text.
Multiple excerpts keep separate span locators. Bound the total returned text for
that section. A repeated call may revisit a section with a narrower query; avoid
wasting context on identical spans without declaring them newly inspected.

Reading three sections does not imply document-wide coverage. A 95k-token document
is navigated by repeated scoped queries, never loaded wholesale into worker model
context. Large-document fixtures will be needed because the current ingested
sections are smaller than the proposed limits.

### Runtime defaults and accounting

```ini
MAX_SECTIONS_PER_READ = 3
MAX_TOKENS_PER_SECTION = 1000
MAX_TOKENS_PER_READ = 3000
KNOWLEDGE_WORKER_MAX_CYCLES = 5
TOTAL_CONTEXT_BUDGET = 30000
FINALIZATION_RESERVE = 4000
EXPLORATION_BUDGET = 26000
MAX_REVIEW_CYCLES = 2
```

Derive `EXPLORATION_BUDGET` from total minus reserve. Reject inconsistent or
nonpositive configuration. The three document-read limits are runtime maxima,
not model-overridable suggestions; a call can request fewer sections.

Budget accounting rules:

1. The 30,000-token budget belongs to one worker invocation. It is the maximum
   planned model context plus reserved finalization capacity, not a sum of repeated
   prompt tokens billed across calls. Track cumulative provider usage separately.
2. Count the actual exploration prompt: instructions, task/context, tool schemas,
   messages, bounded observations, and serialization overhead. Use a tokenizer
   appropriate to the configured model and conservative overhead/headroom. Validate
   that the chosen model supports the configured budget; do not silently raise it.
3. The 26,000 exploration allocation includes model-generated decision/tool-call
   messages as well as tool results. Cap decision output before each model call
   and account for it before admitting the resulting tool requests.
4. Treat 1,000 tokens as the maximum returned source text per section. The 3,000
   read cap covers the complete model-facing result, including metadata and JSON
   overhead, so three sections may each contain less than 1,000 tokens. Measure
   and enforce all three limits after serialization.
5. Before each tool call, require enough remaining exploration space for its
   enforced maximum result plus message overhead. Every tool adapter, including
   search and MCP, must have a bounded result contract. Start with one pending
   tool call at a time; any later batching must reserve the sum of all pending
   outputs atomically. Retrying never resets counters or expands limits.
6. Do not execute a requested expansion whose maximum result cannot fit. Set
   `exploration_closed=True`, record `context_budget`, and route to finalization.
   Do not spend the finalization reserve on one more retrieval.
7. After execution, validate the returned payload and remeasure before adding it
   to model context. An adapter overrun must not enter context unbounded: return
   a bounded structured failure/partial result and preserve exact spans for any
   returned text. Never clip structured JSON into an invalid or misleading record.
   Include error envelopes in budget estimates too.
8. Recheck after each observation and before each model call. Enforce cycles,
   tool-call limits, timeouts, and request deadlines separately; available context
   does not permit unbounded execution. A cycle is one decision plus its selected
   action(s)/observations; finalization is outside the five exploration cycles.
9. The 4,000-token reserve covers additional finalization instruction/schema
   overhead and generated draft output. Existing task/evidence context remains
   within the exploration allocation. Explicitly budget the final prompt plus
   output within 30,000; the reserve is not permission for a further 4,000-token
   input and another 4,000-token output. No automatic summarization/research loop
   is added to recover context in this milestone.

Token counting is runtime control, not a semantic judgment. A provider context
error or tokenizer mismatch remains an explicit execution failure and must not
silently relax the configured limits.

### Worker finalization and result

Deterministic code may close exploration and route execution. It must not write
factual claims, decide what the sources prove, or fabricate a partial answer.

```text
Decision LLM
  -> tool requested
  -> pre-call budget check
       insufficient -> close exploration --------------------+
       sufficient   -> tool -> measure/admit observation     |
                                -> post-call budget check    |
                                     continue -> Decision    |
                                     stop -------------------+
                                                             v
                                                Worker finalization LLM
                                                             |
                                                KnowledgeWorkerDraftResult
                                                             |
                                                Evidence materializer
                                                             |
                                                KnowledgeWorkerResult
```

Normal completion and cycle exhaustion also route to the same tool-free worker
finalizer. It receives the objective, observed evidence, unresolved needs, failure
records, and runtime termination reason. It selects supported claims and evidence
references in a draft; deterministic materialization then validates and replaces
those selections with evidence IDs. This worker finalizer is distinct from the
user-facing Final Answer Generator in Phase 3.

Extend the architecture's result contract rather than dropping provenance fields:

```python
class KnowledgeWorkerResult(BaseModel):
    task_id: str
    status: Literal["answered", "partial", "not_found", "needs_clarification"]
    termination_reason: Literal[
        "completed", "cycle_limit", "context_budget", "tool_failure"
    ]
    claims: list[SupportedClaim]
    unresolved: list[UnresolvedItem]
    source_conflicts: list[SourceConflict]
    clarification: ClarificationRequest | None
    tool_failures: list[ToolFailure]
```

Runtime owns `termination_reason`; the LLM owns the semantic result status and
claims. Preserve the same reason on the draft and final result. Status and reason
are independent: a limit does not mechanically mean `partial` if the objective is
already fully supported. Conversely, exhausting budget with no claims is not proof
of absence; `partial` may have an empty claims list and explicit unresolved needs.
Use `not_found` only when the attempted source coverage supports that bounded
outcome, never as a generic label for failed tools or budget exhaustion.

A recoverable tool failure can be followed by further exploration within budget;
record it without automatically ending the worker. Use `tool_failure` when failure
actually forces exploration to stop. Preserve the first stopping reason if limits
coincide; counters/failure details explain other constraints. Cancellation and a
failed finalization model call remain execution failures, not invented semantic
results. Bound retries and leave time within the request deadline for finalization
when possible.

Required wording behavior: "The inspected sections did not establish the
replication mode, and exploration ended due to budget." Do not strengthen this to
"The document does not specify it." The Supervisor and final answer must preserve
that distinction.

## Phase 1 tasks: contracts and source adapters

- [x] **P1.1 — Define domain contracts and runtime configuration.** Add plans,
  tasks, source references, observations, draft/final worker results, evidence,
  conflicts, clarification, failures, answer packages, and review decisions.
  Include the defaults/accounting above, bounded payloads, model configuration,
  tool deadlines and overall task/run limits. Source references cover documents,
  service/team data, employees, incidents, shifts, and deployments explicitly.
- [x] **P1.2 — Load the published document release.** Validate the handoff and
  source hashes/locators; pin a release per run. Resolve stable document versions,
  sections and passages. Keep source-store paths internal and report missing or
  mismatched artifacts explicitly. Do not construct a second ingestion pipeline.
- [x] **P1.3 — Implement knowledge search.** Reuse ingestion's provider access
  where appropriate, query dense and BM25 branches with the same semantic filters,
  merge/deduplicate by source identity, and bound candidate snippets/top-k.
  Record scores and source attribution without claiming search recall is complete.
  Access-policy filters are deferred, not silently represented as implemented.
- [x] **P1.4 — Implement document expansion.** Implement the exact signature,
  document-scoped section selection, optional exact IDs, excerpt/span semantics,
  result contract, and all three read limits above. Keep repeated navigation
  available without whole-document model input.
- [x] **P1.5 — Implement the application MCP adapter.** Discover/validate the seven
  existing tools; manage connection lifecycle, schema validation, bounded retries,
  cancellation and errors. Preserve snapshot/time/record provenance, employee
  search truncation, and shift-range errors. Expose actual tool names, including
  `get_oncall` and `get_current_deployment`; do not advertise missing searches.
- [x] **P1.6 — Verify adapter contracts.** Use isolated fixtures and local protocol
  checks. Prove stable locators, matching filters, exact source spans, malformed
  ID handling, payload bounds, and unavailable-source behavior. Add an opt-in
  hosted smoke check against the published release; keep offline checks repeatable.

Exit: both source families can supply bounded attributable observations without
an agent. Validate a synthetic 95k-token document, a section over 1,000 tokens,
Unicode/serialization overhead, repeated narrower queries, and explicit section
IDs. No individual read exceeds its effective limits.

## Phase 2 tasks: bounded Knowledge Worker

- [x] **P2.1 — Build private worker state and decision loop.** Keep task, cycle,
  observations, token counters, pending-call reservations and control flags in
  the subgraph. Bind only the two document tools and seven MCP tools. Resolve
  dependent lookup chains locally; do not prescribe fixed source trajectories.
- [x] **P2.2 — Enforce budgets and stopping.** Implement checks before decisions,
  before tools, and after results; runtime closes exploration at limits. A blocked
  tool is never executed. Preserve budget/cycle counters through retries and
  checkpoint recovery; a finalization transition cannot restart exploration.
- [x] **P2.3 — Add the worker finalization LLM.** Use the reserved capacity and no
  tools. Produce a schema-valid draft with explicit unresolved needs and selected
  observations. Treat normal completion, limits, clarification and unavailable
  evidence as legitimate outcomes; preserve runtime termination metadata.
- [x] **P2.4 — Materialize selected evidence deterministically.** Verify each
  selected reference occurred in this task, bind it to the exact observed
  representation/spans, hash/snapshot it, and assign stable evidence IDs. Reject
  fabricated references or content expansion. Keep claim IDs unique and premise
  references resolvable; distinguish support, conflict and context links.
- [x] **P2.5 — Verify worker behavior.** Cover document navigation, a dependent
  MCP lookup chain, mixed sources, exact budget boundary, blocked expansion,
  cycle exhaustion, malformed output, tool recovery and finalization failure.
  Assert that deterministic control code never creates semantic claims.

Exit: one objective returns a valid `KnowledgeWorkerResult` plus selected
evidence, or an explicit execution failure. Tests must show finalization runs
after the fifth allowed tool cycle and after a pre-call budget rejection. Include
the replication-mode partial-answer example, plus exhaustion before any useful
evidence and a fully answered objective at a limit. Repeated reads or retries
cannot evade counters or promote unread document text to evidence.

## Phase 3 tasks: four-role graph with sequential workers

- [x] **P3.1 — Add Supervisor planning and dispatch.** Give it static capability
  descriptions, conversation context and structured contracts. Plan the minimum
  bounded objectives; validate task IDs/dependencies and reject cycles. Execute
  sequentially first, keeping dependent local lookup chains inside one task.
- [x] **P3.2 — Add synthesis and structural checks.** Build the answer package
  from worker results/evidence only. Validate claim/evidence/premise IDs and
  derivation relationships. Preserve unresolved needs, source conflicts,
  temporal qualifiers, and budget-limited coverage; no new retrieval here.
- [x] **P3.3 — Add Reviewer and targeted repair routing.** Use a narrow input
  projection and no retrieval tools. Route approved packages to final rendering.
  For revision, let Supervisor repair from existing evidence or schedule bounded
  follow-up worker tasks for missing information, preserving valid work.
- [x] **P3.4 — Enforce review termination and clarification.** Define
  `MAX_REVIEW_CYCLES=2` as at most two Reviewer evaluations, including the initial
  evaluation: one repair opportunity. A second rejection terminates with a
  controlled workflow failure, never an unapproved factual answer. Count all
  follow-up workers against the run's total task/deadline limits. A worker
  clarification becomes a reviewed user question and ends the current run; the
  reply starts a fresh run using conversation context.
- [x] **P3.5 — Add Final Answer Generator and citations.** Supply only the
  approved package and selected evidence, no tools. Render citations
  deterministically; verify nonempty output and known evidence IDs. Evaluate
  preservation of meaning, uncertainty and temporal scope separately from
  structural citation checks. Final-generation failure is an execution failure.
- [x] **P3.6 — Verify complete graph paths.** Cover document-only, MCP-only,
  mixed-source, clarification, unavailable sources, worker partial results,
  targeted research repair and exhausted review. Test injected source instructions
  as data. Assert that only the approved route reaches final generation and that
  no hidden authoring/evaluation files are used as retrieval sources.

Exit: the four roles produce reviewed, cited answers through an executable graph
harness. Document-only questions avoid gratuitous MCP; operational responses cite
the frozen timestamp; incomplete inspection does not become document-wide absence.
No claims of collection analytics or authorization coverage are made.

## Phase 4 tasks: application integration and concurrency

- [x] **P4.1 — Wire runtime and packaging.** Replace the mock graph through an
  explicit configured mode, supply model/tool clients and settings, include the
  MCP client dependency in the application image, and mount the source store and
  published release together. Reuse API startup/shutdown and readiness conventions.
- [x] **P4.2 — Integrate final output and activity streaming.** Update the current
  `mock_node`-specific event adapter. Emit bounded stage/tool/budget/review status;
  expose final answer text only after approval and render validation. Keep worker
  scratch messages and raw payloads out of public answer events. Reuse SSE replay
  storage; add no parallel custom event history to graph business state.
- [x] **P4.3 — Implement follow-ups and checkpoint recovery.** Reset per-turn
  plans/results/evidence selection/review state while retaining conversation.
  Resolve references from earlier turns but refresh operational lookups when
  needed. Recover pending work without resetting limits or mixing earlier task
  results into the active run. Keep prompt ambiguity separate from authorization.
- [x] **P4.4 — Enable independent parallel workers.** Use native graph fan-out,
  bounded concurrency and joins. Give each worker its own 30,000-token budget;
  enforce shared run task/deadline limits too. Define collision-safe run/task/
  attempt/evidence IDs and deterministic replacement for revised results.
- [x] **P4.5 — Extend observability.** Trace selected roles, tool outcomes,
  durations, cycle/token usage, stopping reasons, evidence selections and review
  decisions. Distinguish estimated context size from provider-reported cumulative
  usage. Ensure tracing cannot alter workflow decisions or fail successful runs.
- [x] **P4.6 — Run application acceptance.** Verify sequential and parallel
  objectives, follow-ups, budget exhaustion, tool outages, cancellation, checkpoint
  recovery, event replay and container source-store availability. Update usage
  docs with configuration, executed checks, and known deferred capabilities.

Exit: the existing UI/API exposes the real four-role flow, bounded activity and
validated final citations. Parallel workers and new turns do not mix evidence or
inherit exhausted/unused budgets incorrectly. Runtime failures remain visible.

## Suggested implementation locations

The implementation uses these locations in the existing application.

| Area | Location |
| --- | --- |
| Domain contracts, worker, evidence materializer, supervisor/reviewer/finalizer | `src/comtech/agents/` |
| Search, published-release reader, document expansion | `src/comtech/retrieval/` |
| Application MCP client adapter | `src/comtech/integrations/northstar.py` |
| Top-level enterprise graph construction | `src/comtech/agents/graph.py` |
| Configuration, API and event integration | Existing `settings.py`, `api/app.py`, `events.py` |
| Focused contract, budget, graph and integration tests | `tests/agents/`, `tests/retrieval/`, existing integration tests |

Do not modify the immutable MCP fixture data or regenerate/index the document
corpus simply to implement these agents. Development/evaluation should test
discovery from actual source interfaces, without copying the brief's expected
answers or story-specific lookup paths into agent prompts.

## Validation and progress tracking

Use deterministic fake-model responses to test routing, budgets and structural
contracts. Use synthetic long-document fixtures for expansion boundaries. Use
real local MCP transport for client behavior, and a small opt-in model/hosted
retrieval smoke suite for semantic end-to-end behavior. Passing scripted graph
tests alone does not establish retrieval quality or model reasoning quality.

For each completed task, check its box and record the relevant checks. At each
phase exit, summarize actual behavior, validation run, and remaining limits here.
Do not run unrelated broad checks repeatedly without a change or unresolved risk.

| Phase | Status | Implementation/validation record |
| --- | --- | --- |
| 1 | Complete | Published-release checksum validation, bounded document discovery/expansion, and seven-tool MCP adapter; synthetic long-document, real local MCP transport, and hosted hybrid-discovery checks passed. |
| 2 | Complete | Pre/post-call budgets, cycle limits, tool-free LLM finalization, immutable observed evidence, and bounded structural correction; boundary, outage, cancellation, and checkpoint-resume checks passed. |
| 3 | Complete | Supervisor, private workers, Reviewer, and Final Answer Generator; dependencies, targeted repair, review cap, citation validation, and operational/documentary/mixed hosted checks passed. |
| 4 | Complete | API/UI mode, final-only answer events, replay, follow-ups, parallel isolation and tracing implemented. Windows: 88 passed, 12 skipped. Linux/PostgreSQL container: 96 passed, 4 hosted checks skipped. API image built; non-root, network-disabled read-only mount check loaded 132 documents and 1,054 sections/passages with cached tokenizer. |

References: [alignment review](enterprise-agents-alignment.md),
[MCP service](../mcp.md), [ingestion/source-store handoff](../ingestion.md),
[recorded ingestion release](../ingestion-run-2026-09-28.md).

## Implementation notes

- The user delegated model selection by role/task complexity: Sol for Supervisor,
  Reviewer and complex workers; Luna for simple workers and final wording. All
  role choices are configurable. See [agent operation](../agents.md).
- Structural draft validation permits one bounded LLM correction attempt using
  the same observations. Runtime returns only validation feedback, performs no
  semantic repair, opens no new retrieval, and rechecks finalization context.
- API checks use isolated PostgreSQL with scripted models; hosted tests separately
  exercise the real providers. Authorization tests remain out of scope.
- The user explicitly approved four hosted smoke tests, their paid OpenAI calls,
  read-only Pinecone queries, and transmission of fictional source content.
- All four hosted smoke checks passed across validation runs. Operational lookup
  initially exposed an invalid supporting-evidence selection; after adding bounded
  LLM correction, its targeted rerun passed. Documentary and mixed results retained
  supported partial findings and explicit unresolved items when exploration ended.
  These checks establish basic integration, not comprehensive retrieval quality.
- The container suite covers the real PostgreSQL API path with tracing disabled
  and Phoenix enabled using scripted models. Windows skips database integration
  checks; hosted checks are opt-in and run separately. No corpus was regenerated
  and no hosted index was modified.
