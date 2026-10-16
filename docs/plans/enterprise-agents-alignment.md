# Initial enterprise agents: architecture alignment review

Status: reviewed; application agents are not implemented by this review.
Date: 2026-09-29.

Follow-up decision: authorization is explicitly deferred for the initial agent
implementation. The [phased implementation tasks](enterprise-agents-implementation.md)
carry this decision and the agreed worker expansion/budget requirements forward.

The four-role design in `enterprise_agent_architecture_v1_3.docx` is a good fit
for the available sources. Keep Supervisor, bounded Knowledge Worker, Reviewer,
and Final Answer Generator. Adjust the source contracts and complete the runtime
control flow before implementing the design literally.

This review treats the architecture document as the suggested agent plan. The
existing MCP and ingestion plans describe earlier infrastructure milestones,
not an implementation of these four agents.

## Evidence and scope

Reviewed the architecture, the `Synthetic Bank Complete Generation Brief (1).docx`,
MCP implementation and schemas, ingestion implementation and handoff documentation,
the current graph/API/event adapter, and metadata manifests. No generated story
documents, canonical story graph, or hidden evaluation answers were opened.
Document counts below come from manifest metadata, not source prose.

This was a static repository review. It did not query hosted Pinecone, exercise a
running MCP endpoint, or rerun tests. The Northstar tools were inspected in the
repository; they are not exposed as callable tools in this assistant session.

## Discovered sources

| Source | Available shape | Authority and use |
| --- | --- | --- |
| Enterprise documents | 132 document versions, 1,054 sections; nine corpora | Historical incidents, decisions, policy versions, procedures, product behavior, control evidence |
| Pinecone search representation | Published local handoff for build `2fddb22824bee702`; 1,186 passage/summary records, nine namespaces | Discovery over documents; ingestion verification is recorded, but application retrieval is not implemented |
| Local source store and hierarchy | Exact source bytes, document/section/passage manifests, hashes, offsets, versioned IDs | Bounded section reading and reproducible citation snapshots; must be deployed with the release artifacts |
| MCP operational snapshot | 21 employees, eight teams, ten services, 20 shifts, three open incidents, ten deployments | Current operational state relative to the frozen snapshot |

The nine document corpora are architecture (18), changes (12), incidents (36),
manuals (4), meetings (8), policies (16), products (14), runbooks (14), and
risk/audit (10). Metadata includes document type, department, service IDs,
version, created/published/effective dates, supersession, section locators, roles,
and entitlements. There are 123 current and nine superseded document versions;
classification counts are 27 general, 80 operations, 21 confidential risk, and
four restricted.

These are two business-source families: documents and structured operational
records. Pinecone and the local source store are two representations of the
document family, not independent corroborating authorities. PostgreSQL stores
workflow/checkpoint and delivery state; it is not a banking knowledge source.
Canonical generation files and evaluation keys must remain outside agent tools.

MCP's `DEMO-2026-09-15-A` snapshot is frozen at `2026-09-15T10:00:00Z`.
"Current" means current at that instant, not the machine date. Shift selection
supports only `[2026-09-15T08:00:00Z, 2026-09-16T08:00:00Z)`.

## Tool contract alignment

Architecture section 7 uses conceptual tool families. Map them to the actual
seven-tool service; no additional MCP servers or specialist agent roles are
needed merely to match those family names.

| Architecture capability | Existing implementation | Required decision/change |
| --- | --- | --- |
| `knowledge_search` | Ingestion and provider verification probes exist | Implement an application adapter over the published release, with dense/BM25 retrieval, metadata filtering and semantic source references |
| `read_document_sections` | Source bytes, outlines, sections and offsets exist | Implement bounded reading by stable document/version/section IDs; default maximum three sections |
| `search_services` | Absent | Do not advertise it. Initially accept exact known IDs or resolve candidates from authorized document metadata, then verify through `get_service`. Add a real catalog discovery endpoint later if required |
| `get_service` | Implemented | Reuse; returns service and owner-team details, including relationship IDs |
| `search_people` | Named `search_employees(query, team_id?)` | Prefer the actual name; an alias must preserve active-only matching, ten-result cap and truncation metadata |
| `get_employee` | Implemented | Reuse; preserve inactive status and nullable manager relationships |
| `search_incidents` with dates, severity, ordering and free text | Only `list_open_incidents(service_id?)` exists | Expose the actual bounded open-list contract. Historical incidents are documents; do not imply a historical incident database exists |
| `get_incident` | Implemented for the frozen open incidents | Preserve its active-record authority; it does not retrieve postmortems |
| On-call lookup | `get_oncall(service_id, at?)` implemented but omitted from architecture examples | Include in the worker capability and source contract |
| Deployment lookup | `get_current_deployment(service_id)` implemented but omitted from architecture examples | Include; deployment timestamp/provenance comes from this tool |

The worker should therefore start with two document tools plus the existing seven
MCP tools. The Supervisor sees their capability descriptions, not concrete tool
schemas. Tool discovery should validate the expected server contract at startup.
No `get_team` is needed for the first scope: `get_service` already returns owner
team details, and employee lookup resolves manager/contact relationships.

## What already aligns

- Semantic decomposition suits mixed historical/current questions. Keep a
  dependent service-to-person-to-manager chain inside one worker objective.
- One worker type can use both source families. Separate source-specific agents
  would add handoffs without being required by the data.
- Private worker observations, selected evidence snapshots, and narrow review
  inputs match the need to distinguish discovery from supporting evidence.
- The design's temporal and uncertainty rules match the brief: symptoms do not
  confirm causes; an old owner is not automatically the current owner; an empty
  open-incident list does not prove health; a proposed action is not approval.
- The existing application already has a LangGraph graph, PostgreSQL checkpointer,
  streaming adapter, and tracing foundation. Reuse those foundations.

## Changes needed before the first implementation

### 1. Adapt source references to actual observations

Extend the architecture's `SourceRef` contract to represent on-call shifts and
deployments explicitly, or document an equally unambiguous typed mapping. Preserve
snapshot ID, source collection, record ID, `as_of`, `updated_at`, and the queried
shift time. Keep the retrieval timestamp separate from source freshness.

For documents use the existing versioned document/section IDs. A section may
eventually contain several passages; a snippet and a full section are different
observations even when they share a semantic locator. Likewise, an incident list
summary and incident detail can refer to the same record with different content.
Add an observation/representation identifier to evidence selection, or enforce an
equivalent unambiguous observation mapping. Materialize only the exact content
observed; never silently expand a selected snippet into unread source text.

Use collision-resistant run/task/claim identities and content-aware evidence
identities. The architecture's dictionary-union reducer is suitable only when
parallel keys cannot conflict. Clarify deduplication scope: cross-task reuse must
not discard which task actually observed and selected the evidence.

### 2. Complete graph routing and termination

The architecture sketch omits executable dispatch/join and dependency handling.
Use native graph fan-out for independent tasks, validate task dependencies, and
join the required results before synthesis. Runtime constraints must bound task
count, parallelism, tool calls, deadlines, and output size as well as the five
worker decision cycles. Allow finalization after the last permitted tool cycle.

Reviewer currently routes revisions only to `supervisor_synthesize`. Define two
outcomes there: repair the package using existing evidence, or dispatch a bounded
follow-up worker objective when evidence is missing. Reviewer itself does not
retrieve. Preserve valid claims and replace the affected result explicitly.

Define precisely what the two-review-cycle limit counts. At exhaustion, never
route an unapproved package to Final Answer Generator. Return a controlled
unresolved/failure outcome, or obtain approval for an explicitly limited package
within the remaining budget. A declared constant alone does not enforce this.

The specification references but does not fully define `SourceConflictDraft`,
`SourceConflict`, `ClarificationRequest`, and `ToolFailure`; complete these
contracts and their transitions before graph wiring. Define how clarification
ends or interrupts a run and how a user response resumes the objective.

### 3. Separate persistent conversation from per-run work

The current graph is still a single deterministic mock node. At a new user turn,
initialize a fresh plan, results, evidence selection, review counter, and answer
package. Checkpointed dictionary reducers otherwise accumulate prior work.
Retain conversation history for follow-up resolution; do not silently treat a
previous turn's operational evidence as a newly observed current result.

Reuse the existing checkpointer for agent state. Existing `app_run_events` serve
SSE delivery/replay; avoid adding another event history inside business state.
The current event adapter emits assistant text only for `mock_node`; update it
for approved final output and bounded activity events. Worker messages, tool
payloads, and unreviewed synthesis must not become user-facing answer text.

### 4. Make source access and deferred scope explicit

The brief requires server-enforced role/scope checks before retrieval and tool
execution. The earlier MCP milestone deliberately deferred these, and ingestion
only preserves access metadata. Architecture v1.3 does not implement them by
describing agents. This is a scope gap, not a reason to redesign the four roles.

Authorization is now explicitly deferred by the user for the initial agent
phases. Use the trusted synthetic development context, retain access metadata,
and do not claim persona/RBAC coverage. Authentication, source/tool authorization,
authenticated thread ownership, and policy-based redaction belong to a later
milestone; they are not prerequisites for this implementation plan. Per-run state
correctness remains in scope. Effective-date filters must follow the question:
historical comparison needs superseded versions, whereas governing policy
selection needs the applicable effective interval.

### 5. Keep collection analytics outside the initial claim of coverage

The brief also requires complete collection discovery, incident deduplication,
and Python calculations. The architecture's five source families and bounded
top-k search do not provide that capability. Keep aggregate/ranking questions
explicitly deferred, returning a limitation when necessary. Later add bounded
collection enumeration and analysis over authorized extracted facts; calculation
outputs are derived results with cited premises, not independent source evidence.

### 6. Preserve reviewed meaning through final rendering

Citation existence checks cannot prove that generated prose preserves every
approved claim's meaning. Retain the proposed no-tools finalizer, validate its
citations deterministically, and evaluate preservation of uncertainty, time, and
scope. Do not describe deterministic citation validation as a semantic proof.
No additional reviewer role is needed merely to start.

## Recommended first milestone

Implement all four roles as one narrow end-to-end slice, initially with one
worker invocation at a time. These are graph roles, not four independently
deployed services. Add parallel worker fan-out after the single-objective path
and evidence boundary pass validation.

1. Finalize contracts, actual capability registry, source authority rules,
   execution context, and budget/termination semantics.
2. Implement document search/section reader and the MCP client adapter; deploy
   the published source hierarchy and original source store together.
3. Build the bounded worker subgraph and deterministic evidence materializer.
4. Add Supervisor plan/synthesis, structural validation, Reviewer routing,
   approved final rendering, and the existing API/UI streaming integration.
5. Validate document-only, MCP-only, mixed-source, and same-session follow-up
   paths; then add independent parallel objectives and targeted research repair.

Acceptance should prove: document-only requests need no MCP; operational answers
carry the frozen timestamp; lookup chains preserve distinct owner/manager/on-call
roles; historical/current comparisons cite the right authority; failed tools do
not trigger invented or stale substitutes; fabricated or unread source references
are rejected; limits terminate; rejected packages cannot reach the finalizer;
and concurrent tasks/new turns do not mix evidence. Add persona isolation tests
when the role-aware milestone is included. Evaluate aggregate questions only
after the collection/analysis capability exists.

## Repository references

- [MCP tool definitions and behavior](../../src/comtech/mcp/tools.py)
- [MCP source and response schemas](../../src/comtech/mcp/models.py)
- [MCP milestone and explicit deferrals](northstar-mcp.md)
- [Document ingestion/source-store contract](../ingestion.md)
- [Recorded hosted ingestion verification](../ingestion-run-2026-09-28.md)
- [Current mock graph](../../src/comtech/graph.py)
- [Application integration](../../src/comtech/api/app.py)
- [Current streaming adapter](../../src/comtech/events.py)
- [Document metadata manifest](../../synthetic_bank/corpus/manifest.jsonl)
- [Operational metadata manifest](../../synthetic_bank/mcp/fixtures/manifest.json)
