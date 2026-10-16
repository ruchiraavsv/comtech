# Northstar MCP server plan

Status: implemented. Usage and verification are recorded in [MCP service](../mcp.md).

Source: `Synthetic Bank Complete Generation Brief (1).docx`, especially Sections
6–8 and Appendix F. This plan follows the user's decision to keep the operational
snapshot frozen and implement the MCP service before client integration or access
rules.

## Outcome and scope

Deliver one containerized, read-only MCP server exposing the seven specified
tools over Streamable HTTP. Multiple independent agents must be able to query the
same server concurrently without changing the snapshot or sharing request state.

This phase includes:

- Operational fixture generation, schemas, consistency checks, and provenance.
- The MCP server, tool discovery, input validation, and tool response contracts.
- Concurrent request isolation and server-side error behavior.
- Container packaging, readiness, lifecycle, and Docker/Podman Compose support.
- Server tests and a protocol smoke-test harness.

Deferred by explicit scope choice:

- Application MCP client, LangGraph integration, routing, memory, and UI changes.
- Client retries, backoff, timeout recovery, reconnection, and application behavior
  when MCP is unavailable.
- Authentication, role/scope enforcement, field redaction, and authorization rules.
- Application rate limiting and full observability-platform integration.
- The complete 60-case golden evaluation suite and document-corpus expansion.

The smoke-test harness is test infrastructure, not the application MCP client.
This milestone will not claim that permission enforcement is implemented. Keep
the service unpublished on the host by default while that work remains deferred.

## Agreed design

```text
Independent test clients / future agents
                 |
                 | Streamable HTTP
                 v
       northstar-mcp Compose service
                 |
       typed tool handlers
                 |
       immutable in-memory snapshot
                 ^
                 |
       validated versioned JSON files
```

- One MCP service exposes all seven tools; no server per tool or per agent.
- JSON is the source fixture format and is loaded once at startup into typed,
  immutable records and lookup indexes. No database is needed for the specified
  bounded lookups against a frozen dataset.
- No runtime writes, file watching, hot reload of fixtures, or machine-clock
  changes to the operational snapshot. A new snapshot requires a new validated
  fixture release and container restart/rebuild.
- Pin a compatible official Python MCP SDK version in the existing lockfile.
  Use the SDK's supported stateless HTTP configuration for this read-only tool
  service, confirming its lifecycle and ASGI integration during implementation.
- Start with one server process capable of concurrent connections. Additional
  workers are not required to support simultaneous callers at this fixture size.
- Keep runtime dependencies limited to the server's actual needs. The service
  must start without Postgres, Pinecone, LLM credentials, or the application API.

## 1. Create the frozen operational dataset

Snapshot ID: `DEMO-2026-09-15-A`.
Reference clock: `2026-09-15T10:00:00Z`.

| Dataset | Planned records | Required relationships and fields |
| --- | ---: | --- |
| Employees | 20 active + 1 inactive former owner | Stable ID, name, title, team, manager, active status, professional contact |
| Teams | 8 | Exact owner-team IDs from Appendix F, display name, manager/contact references |
| Services | 10 | Exact service IDs, domain, owner team, tier, dependencies, rotation |
| On-call shifts | 20 | Two consecutive primary shifts per service; employee, rotation, level, start/end |
| Open incidents | 3 | Exact incident IDs, service, status, severity, symptoms, commander, timestamps |
| Current deployments | 10 | One per service; version, deployment time, change reference, environment |
| Snapshot manifest | 1 | Schema version, clock, fixture horizon, file hashes, record counts |

Every operational record has a stable record ID, `snapshot_id`, and `updated_at`.
Use `northstar.example` for fictional professional email addresses.

Preserve the brief's named employees:

- E1043 Alice Chen: MerchantConnect primary on call and incident commander.
- E1044 Daniel Wong: Payments Platform Reliability manager.
- E2031 Priya Rao: Settlement Platform manager and SettlementHub incident commander.
- E2050 Ravi Perera: PayFlow primary on call and incident commander.
- E3042 Maya Fernando: Fraud Platform manager.

Preserve the three active incident records:

| Incident | Service | Severity | Status | Evidence boundary |
| --- | --- | --- | --- | --- |
| INC-LIVE-1042 | merchantconnect | SEV-1 | investigating | Timeouts and 96% outbound utilization; root cause unconfirmed |
| INC-LIVE-1051 | payflow | SEV-2 | mitigating | Checkout latency and growing retry queue |
| INC-LIVE-1054 | settlementhub | SEV-2 | monitoring | Corporate report delivery delay |

Proposed explicit fixture horizon: `[2026-09-15T08:00:00Z,
2026-09-16T08:00:00Z)`. Each service receives an 08:00–20:00 shift and a
20:00–08:00 shift. Alice covers MerchantConnect's first shift; a different active
employee covers its second. Choose a SettlementHub primary distinct from Priya
so the distinction between commander and on-call responder is exercised.

Treat shift intervals as start-inclusive and end-exclusive. Future scheduled
shifts can be known at the reference clock; they do not advance the snapshot.
Record the requested shift-selection time separately from the snapshot's `as_of`.

Keep MerchantConnect's pinned current version `4.7.2`. Assign other deployment
versions, dates, and unspecified personnel details explicitly, then freeze them.
For FraudShield, distinguish model identity from application/configuration
version where needed. Resolve deployment change references against canonical
history; add explicit canonical change entities where no document slot exists.

Derive shared service names, history, and change links from existing canonical
facts. Add a separate canonical operational snapshot input rather than changing
historical documents to contain live answers. Copy only the resulting operational
fixtures into the runtime image.

## 2. Close the story-specific data relationships

| Story | MCP evidence supplied in this phase |
| --- | --- |
| S1 | MerchantConnect symptoms, current service owner, applicable shift and contact |
| S2 | Current deployment and owner; historical duplicate-payment explanations remain documents |
| S3 | Current SettlementHub incident and declared service dependencies |
| S4 | No MCP evidence needed for the historical policy explanation |
| S5 | Current FraudShield deployment/model identity and ownership |
| S6 | Current incident, service responsibility, and directory contact for the relevant approval role |
| S7 | Explicit current privileged-review responsibility, separate from historical closure evidence |
| S8 | Relevant open-incident observations only; no general regional-health claim |
| S9 | Join incident → service → shift → employee for triage and handover |
| S10 | Current MerchantConnect owner is Payments Platform Reliability; preserve the original design owner in documents |

Resolve contact paths within the existing seven tools:

- `get_service` should expose enough owner-team/rotation/contact identifiers for
  follow-up queries; there is no `get_team` tool in the contract.
- Define searchable employee fields explicitly: name, employee ID, title, and team
  name, with an optional exact `team_id` filter. Team-name search gives a usable
  path without accepting an empty or wildcard-only query.
- Represent the privileged-access review control's responsible employee as an
  explicitly named responsibility on the relevant AuthHub service record.
  Document this fixture assumption; a generic service owner is not automatically
  the owner of every control associated with the service.
- Represent the capacity-change approval contact role explicitly. Identifying a
  contact never implies that approval was granted. Workflow authorization and
  execution are out of scope, and no mutating tool is added.
- Preserve Appendix F's dependency edges, including cycles. Validate references,
  not an assumption that the dependency graph must be acyclic. No recursive
  traversal endpoint is needed.
- The three fixed incidents do not establish universal regional health. Do not
  invent an additional regional incident to fill this optional story branch.

## 3. Implement the seven read-only tools

| Tool | Server behavior |
| --- | --- |
| `search_employees(query, team_id?)` | Case-insensitive documented matching; active matches only; stable ordering; maximum ten results; report truncation |
| `get_employee(employee_id)` | Return the selected employee, including explicit inactive status when applicable |
| `get_service(service_id)` | Return ownership, dependencies, tier, rotation, and explicit responsibility references |
| `get_oncall(service_id, at?)` | Default to the frozen clock; normalize valid timestamps; select the covering shift |
| `list_open_incidents(service_id?)` | Return bounded summaries of the three open incidents, filtered by service when provided |
| `get_incident(incident_id)` | Return active incident detail; never retrieve a historical postmortem |
| `get_current_deployment(service_id)` | Return the current deployment and its timestamp/change provenance |

Validate ID syntax separately from record existence. Reject blank or wildcard-only
directory queries and queries over 80 characters. Reject malformed timestamps;
return `OUT_OF_SNAPSHOT_RANGE` when the requested shift time falls outside the
fixture horizon. Use deterministic ordering and explicit output schemas.

Success responses carry `snapshot_id`, `as_of`, `source`, and stable record IDs.
For collections, retain IDs per result and identify the snapshot collection.
No-result searches return an empty successful result; a valid unknown individual
ID returns `NOT_FOUND`. A known service with no open incidents returns an empty
list without asserting that the service is healthy.

Use SDK-supported tool error signaling and a machine-readable error payload for
`INVALID_ARGUMENT`, `NOT_FOUND`, and `OUT_OF_SNAPSHOT_RANGE`. Keep expected tool
errors distinct from protocol-level errors and unexpected internal failures.
Do not expose stack traces as tool results. `FORBIDDEN` and redaction behavior
are deferred with permissions; do not install a pretend authorization layer.

Prepare test-only adapters for delayed/failing lookups so server behavior can be
exercised without global mutable fault switches or extra public tools. These can
produce the brief's `TIMEOUT` and `UNAVAILABLE` conditions; application retry or
fallback responses remain deferred. Do not ship a public fault-injection API.

## 4. Support simultaneous independent callers

- Load and validate the snapshot before accepting tool requests.
- Keep records immutable, including nested collections, or prevent mutation
  through a repository interface and return independent response objects.
- Do not keep a global current user, selected service, requested timestamp,
  response object, or conversation. Request-specific values stay in the request.
- Implement nonblocking request handling; short in-memory lookups need no
  serialized file access or global query lock. Test delays must yield execution.
- Use MCP request correlation correctly so simultaneous results return to the
  originating requests. Protocol handling belongs to the SDK.
- Ensure one delayed, failed, or cancelled request cannot mutate another result,
  change the snapshot clock, or block unrelated ready lookups.

Initial acceptance target: 50 overlapping tool calls from multiple independent
MCP connections. This is a functional concurrency target, not a promised RPS or
latency SLA. Include distinct services and `get_oncall` timestamps on opposite
sides of the handoff. Verify isolation under one intentionally delayed request.

## 5. Package and run in Compose

- Add a dedicated `mcp` image target using the repository's Python 3.12/uv setup
  and pinned dependencies. Run as non-root with an exec-form startup command.
- Copy the server package and the small fixture directory into the image. Exclude
  canonical truth, hidden expected answers, source documents, and credentials.
- Provide a module entry point independent of application settings that require
  database or hosted-service configuration.
- Bind to `0.0.0.0:8001` inside the container, with `/mcp` as the MCP endpoint.
  Configure SDK host/origin protections for the intended Compose hostname rather
  than disabling them wholesale.
- Add `northstar-mcp` to Compose. Container peers address it as
  `http://northstar-mcp:8001/mcp`; do not publish a host port in the normal stack.
- No persistent volume or writable fixture mount is needed. Frozen fixtures are
  versioned with the image. Development access can use a one-shot test container.
- Expose `/health/live` and `/health/ready`. Readiness follows completed fixture
  validation and reports the schema/snapshot identity without returning records.
- Invalid fixtures cause clear startup failure and a nonzero exit, not a partially
  ready server. Missing required configuration must likewise fail explicitly.
- Set a stop grace period, handle termination, and emit concise structured
  stdout/stderr logs: tool name, request correlation, duration, outcome, snapshot.
  Do not log entire fixture records or contact payloads by default.
- Do not change API readiness, API startup dependency policy, or client connection
  settings in this phase. Only the test runner depends on MCP health.
- Reuse the existing Podman machine and Compose wrappers. Verify portable Compose
  configuration and document what was actually exercised; do not claim Docker
  runtime testing if only Podman was available.

## 6. Validation and acceptance

Fixture checks:

- Exact fixed service/team/incident IDs, named employees, and record counts.
- Unique IDs, resolvable relationships, consistent snapshot IDs and timestamps.
- Every service has an owner team, a deployment, and covering primary shifts.
- All assigned responders are active; no shift gaps or overlaps within the horizon.
- Correct 10:00 selection and exact 20:00 handoff behavior.
- Every incident resolves to its service and commander, who need not be on call.
- Current deployment fields agree wherever repeated; current observations do not
  contradict canonical historical facts or claim confirmed causes from symptoms.
- Repeated fixture generation produces byte-identical outputs.

Server checks:

- Real MCP discovery exposes exactly the seven intended tools and valid schemas.
- Every tool returns its intended payload, provenance, empty result, or error.
- Invalid arguments, unknown IDs, inactive staff, out-of-range timestamps, and
  case-insensitive directory searches behave as documented.
- Full S9 lookup chain reaches Alice through IDs at the frozen clock.
- Concurrent independent callers receive correct, isolated results; one delayed
  call does not prevent unrelated lookups from completing.
- Direct tests verify that result handling cannot mutate the shared fixture.
- Test-only timeout/unavailability behavior produces no invented replacement data.

Container checks:

- Reproducible image build; startup needs no application database or external API.
- Container health becomes ready only after valid fixture loading.
- A sibling test container can complete discovery and tool calls via service DNS.
- Restart preserves the snapshot and tool results. This validates server
  reproducibility, not application reconnection logic.
- Graceful stop and explicit failure with invalid fixture input.

## Proposed implementation layout

```text
src/comtech/mcp/
  __init__.py
  __main__.py
  settings.py
  models.py
  repository.py
  tools.py
  server.py
synthetic_bank/
  canonical/operational_snapshot.json
  mcp/fixtures/
    manifest.json
    employees.json
    teams.json
    services.json
    oncall_shifts.json
    open_incidents.json
    deployments.json
  scripts/generate_mcp_fixtures.py
  scripts/validate_mcp_fixtures.py
tests/mcp/
  test_fixtures.py
  test_tools.py
  test_transport.py
compose.mcp-test.yaml
docs/mcp.md
```

Update the existing document-only validator so adding `synthetic_bank/mcp/` no
longer fails its scope assertion. Preserve its document integrity checks and
index allowlist; neither operational fixtures nor canonical snapshots belong in
the document index. Keep document and MCP validation reports distinct.

## Implementation order and completion criteria

1. Define schemas and explicit fixture assumptions; generate and validate JSON.
2. Implement the immutable repository and seven deterministic tool handlers.
3. Expose MCP over HTTP with health endpoints and lifecycle handling.
4. Add real-protocol tests and prove concurrent request isolation.
5. Add the image target, Compose service, isolated container tests, and usage docs.

The milestone is complete when a containerized server independently serves all
seven tools from the correct frozen snapshot, satisfies the story data joins,
passes concurrency and lifecycle checks, and can be exercised without the client
application. Client behavior and permission enforcement remain clearly deferred.
