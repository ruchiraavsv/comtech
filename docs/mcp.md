# Northstar MCP service

One read-only MCP service serves 72 operational records from immutable JSON:
21 employees, eight teams, ten services, 20 on-call shifts, three open incidents,
and ten deployments. No database or provider credentials are required.

The snapshot is `DEMO-2026-09-15-A`, frozen at `2026-09-15T10:00:00Z`.
The operational source is `synthetic_bank/canonical/operational_snapshot.json`;
only its generated `synthetic_bank/mcp/fixtures/` files enter the runtime image.
Historical documents and private canonical authoring records stay outside it.

## Run

From the repository root, using Python 3.12:

```powershell
py -m uv sync --extra mcp
py -m uv run --frozen --extra mcp python -m comtech.mcp
```

The local endpoint is `http://127.0.0.1:8001/mcp`. For the existing Compose stack:

```powershell
./scripts/compose.cmd up --build -d northstar-mcp
```

Sibling containers use `http://northstar-mcp:8001/mcp`. Compose publishes no host
port for this service. It runs independently of the API and database, as a
non-root user with a read-only filesystem and temporary `/tmp` storage.
The remote Compose overlay enables `unless-stopped` restarts.

The transport is stateless MCP Streamable HTTP with JSON responses, using the
official Python SDK (locked to 2.2.0). Health endpoints are `/health/live` and
`/health/ready`. Readiness requires successful schema, checksum, relationship,
and story-invariant validation; invalid fixture input fails startup. Shutdown
allows ten seconds for requests within Compose's 15-second grace period.

Standalone settings use the `NORTHSTAR_MCP_` prefix and never load the application's
`.env`. Available settings are `HOST`, `PORT`, `FIXTURE_DIRECTORY`,
`LOOKUP_TIMEOUT_SECONDS` (default five), `ALLOWED_HOSTS`, and `ALLOWED_ORIGINS`.
The last two accept JSON arrays. Defaults allow localhost, loopback, and the
Compose service name. Configure them explicitly if the service DNS changes.

## Tools and response contract

| Tool | Arguments |
| --- | --- |
| `search_employees` | `query`, optional `team_id` |
| `get_employee` | `employee_id` |
| `get_service` | `service_id` |
| `get_oncall` | `service_id`, optional timezone-aware ISO timestamp `at` |
| `list_open_incidents` | optional `service_id` |
| `get_incident` | `incident_id` |
| `get_current_deployment` | `service_id` |

Discovery includes input and output JSON schemas. Successful results expose
`snapshot_id`, `as_of`, `source`, `record_id`, and typed `payload`, both as MCP
structured content and JSON text. For example, call `get_service` with
`{"service_id":"merchantconnect"}`, then use the returned identifiers to look
up its primary shift and employee.

Employee search returns at most ten active staff, with total and truncation
metadata. Direct employee lookup can return an explicitly inactive employee.
On-call coverage is `[2026-09-15T08:00:00Z, 2026-09-16T08:00:00Z)` with a 20:00 UTC
handoff. Omitting `at` uses the frozen clock, never wall-clock time.

Tool failures set MCP `isError` and return snapshot/source metadata plus
`error.code` and `error.message`. Codes are `INVALID_ARGUMENT`, `NOT_FOUND`,
`OUT_OF_SNAPSHOT_RANGE`, `TIMEOUT`, `UNAVAILABLE`, and `INTERNAL_ERROR`.
Unavailability injection exists only in tests. Cancellation propagates normally.
Unknown records and failures never produce replacement facts. An empty incident
list does not establish service health or regional health.

Each request reads the same immutable in-memory indexes and builds its own result.
There are no per-client mutable records or shared request state. Logs contain tool
name, request identifier, outcome, duration, and snapshot identity, without tool
arguments or employee contact details.

## Story alignment and regeneration

Fixtures preserve the brief's service dependencies, current owners, incident
commanders, deployment references, and contact lookup paths. MerchantConnect's
capacity-approval contact and AuthHub's privileged-review control owner are
explicit fixture assumptions with document provenance. Naming a contact does
not grant approval authority. Active incident symptoms are not presented as
confirmed root causes. S4 remains document-only; no general regional telemetry
is invented for S8. The validation report records coverage for S1–S10.

Regenerate historical documents first if their canonical source changed, then:

```powershell
py synthetic_bank/scripts/generate_mcp_fixtures.py
py -m uv run --frozen --extra mcp python synthetic_bank/scripts/validate_mcp_fixtures.py
```

Generation is deterministic. Restart or rebuild the service to load a regenerated
snapshot; no hot reload is provided. Operational data is excluded from the
historical document index. MCP and document validation reports are separate.

## Verification

```powershell
py -m uv run --frozen --extra mcp pytest tests/mcp -q
podman compose -p comtech-mcp-tests -f compose.mcp-test.yaml up --build --abort-on-container-exit --exit-code-from tests
podman compose -p comtech-mcp-tests -f compose.mcp-test.yaml down
```

Docker Compose can use the same file by replacing `podman compose` with
`docker compose`. Verification on Windows Python and Linux containers through
Podman Compose passed all 32 MCP tests. The suite covers all seven tools over real
HTTP, 50 calls from ten independent clients, shift boundaries, fixture corruption,
request isolation, timeout/cancellation behavior, discovery schemas, transport
host/origin validation, and lifecycle reproducibility. The Compose run also
verified service-DNS access, readiness, and graceful shutdown.

A subsequent container restart passed discovery and tool assertions again.
Missing fixtures caused a nonzero startup exit, and image inspection confirmed
that canonical documents and the database driver are absent. Regenerating the
fixtures produced byte-identical files. The full Python suite passed 42 tests
with six integration tests skipped; document validation and its four mutation
tests also passed.

Application integration, client retries and outage behavior, authentication,
permissions, and redaction remain deferred as agreed. This milestone implements
the standalone service and its fixtures; the application does not call it yet.
