"""Typed read-only queries and their stable error contract."""

import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime

import mcp_types as types
from pydantic import ValidationError

from .models import (
    CLOCK,
    SNAPSHOT_ID,
    Deployment,
    Employee,
    EmployeeArgs,
    EmployeeMatch,
    EmployeeMatches,
    Incident,
    IncidentArgs,
    IncidentSummary,
    OncallArgs,
    OncallDetails,
    OpenIncidentArgs,
    OpenIncidents,
    Response,
    SearchArgs,
    ServiceArgs,
    ServiceDetails,
)

LOGGER = logging.getLogger("comtech.mcp")
TOOL_SPECS = {
    "search_employees": (
        SearchArgs,
        EmployeeMatches,
        "Search active staff by name, ID, title or team name. Literal "
        "case-insensitive substring; at most ten matches.",
    ),
    "get_employee": (
        EmployeeArgs,
        Employee,
        "Get an employee and explicit active status from the frozen directory.",
    ),
    "get_service": (
        ServiceArgs,
        ServiceDetails,
        "Get current service ownership, dependencies, rotation and named responsibility contacts.",
    ),
    "get_oncall": (
        OncallArgs,
        OncallDetails,
        "Get the primary shift covering at, or the frozen clock. "
        "Intervals include start and exclude end.",
    ),
    "list_open_incidents": (
        OpenIncidentArgs,
        OpenIncidents,
        "List frozen open incidents, optionally for a service. No "
        "incidents does not establish service health.",
    ),
    "get_incident": (
        IncidentArgs,
        Incident,
        "Get a frozen active incident. Historical postmortems and confirmed "
        "causes inferred from symptoms are not provided.",
    ),
    "get_current_deployment": (
        ServiceArgs,
        Deployment,
        "Get the snapshot deployment version, change reference and "
        "model/configuration identity when applicable.",
    ),
}


class ToolFailure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def tool_definitions():
    return [
        types.Tool(
            name=name,
            description=description,
            input_schema=args.model_json_schema(),
            output_schema=Response[output].model_json_schema(),
            annotations=types.ToolAnnotations(
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        )
        for name, (args, output, description) in TOOL_SPECS.items()
    ]


def fail(code, message):
    raise ToolFailure(code, message)


class ToolService:
    def __init__(self, snapshot, *, before_call=None, timeout_seconds=5.0):
        self.snapshot = snapshot
        # Dependency injection for isolated tests only; never exposed through tool arguments.
        self.before_call = before_call
        self.timeout_seconds = timeout_seconds

    def require_record(self, table, key):
        row = self.snapshot.get(table, key)
        if row is None:
            fail("NOT_FOUND", "No record matches the supplied identifier in this snapshot.")
        return row

    def query(self, name, args):
        snapshot = self.snapshot
        if name == "search_employees":
            if args.team_id is not None:
                self.require_record("teams", args.team_id)
            matches = []
            for employee in snapshot.rows("employees"):
                if not employee.active or (
                    args.team_id is not None and employee.team_id != args.team_id
                ):
                    continue
                team = snapshot.get("teams", employee.team_id)
                fields = (employee.name, employee.employee_id, employee.title, team.name)
                if any(args.query.casefold() in value.casefold() for value in fields):
                    matches.append(employee)
            matches.sort(key=lambda e: (e.name.casefold(), e.employee_id))
            items = tuple(
                EmployeeMatch.model_validate(e.model_dump(include=set(EmployeeMatch.model_fields)))
                for e in matches[:10]
            )
            return (
                "employees",
                "employees",
                EmployeeMatches(
                    items=items, total_matches=len(matches), truncated=len(matches) > 10
                ),
            )
        if name == "get_employee":
            return "employees", args.employee_id, self.require_record("employees", args.employee_id)
        if name == "get_incident":
            return (
                "open_incidents",
                args.incident_id,
                self.require_record("open_incidents", args.incident_id),
            )
        if name == "list_open_incidents":
            if args.service_id is not None:
                self.require_record("services", args.service_id)
            rows = sorted(
                (
                    i
                    for i in snapshot.rows("open_incidents")
                    if args.service_id is None or i.service_id == args.service_id
                ),
                key=lambda i: i.incident_id,
            )
            summaries = tuple(
                IncidentSummary.model_validate(
                    i.model_dump(include=set(IncidentSummary.model_fields))
                )
                for i in rows
            )
            return "open_incidents", "open_incidents", OpenIncidents(items=summaries)
        service = self.require_record("services", args.service_id)
        if name == "get_service":
            return (
                "services",
                service.record_id,
                ServiceDetails(
                    service=service, owner_team=snapshot.get("teams", service.owner_team_id)
                ),
            )
        if name == "get_current_deployment":
            deployment = snapshot.deployment(service.service_id)
            return "deployments", deployment.record_id, deployment
        if name == "get_oncall":
            at = snapshot.as_of
            if args.at is not None:
                if not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})",
                    args.at,
                ):
                    fail("INVALID_ARGUMENT", "at must be an ISO 8601 timestamp with a timezone.")
                try:
                    at = datetime.fromisoformat(args.at.replace("Z", "+00:00")).astimezone(UTC)
                except ValueError:
                    fail("INVALID_ARGUMENT", "at is not a valid timestamp.")
            if not snapshot.horizon_start <= at < snapshot.horizon_end:
                fail("OUT_OF_SNAPSHOT_RANGE", "Requested time is outside the fixture horizon.")
            shift = next(
                s for s in snapshot.shifts(service.service_id) if s.starts_at <= at < s.ends_at
            )
            return "oncall_shifts", shift.record_id, OncallDetails(queried_at=at, shift=shift)
        fail("INVALID_ARGUMENT", "Unknown tool.")

    async def call(self, name, arguments, request_id=None):
        started = time.monotonic()
        outcome = "OK"
        try:
            if name not in TOOL_SPECS:
                fail("INVALID_ARGUMENT", "Unknown tool.")
            input_model, output_model, _ = TOOL_SPECS[name]
            try:
                args = input_model.model_validate(arguments if arguments is not None else {})
            except ValidationError:
                fail("INVALID_ARGUMENT", "Arguments do not match the tool's input schema.")
            async with asyncio.timeout(self.timeout_seconds):
                if self.before_call is not None:
                    await self.before_call(name, args)
                table, record_id, payload = self.query(name, args)
            response = Response[output_model](
                source=f"northstar:{table}", record_id=record_id, payload=payload
            )
            body = response.model_dump(mode="json")
            return types.CallToolResult(
                content=[types.TextContent(text=json.dumps(body))], structured_content=body
            )
        except asyncio.CancelledError:
            outcome = "CANCELLED"
            raise
        except Exception as exc:
            if isinstance(exc, ToolFailure):
                code, message = exc.code, exc.message
            elif isinstance(exc, TimeoutError):
                code, message = "TIMEOUT", "The server-side lookup deadline was exceeded."
            else:
                code, message = "INTERNAL_ERROR", "The server could not complete the lookup."
            outcome = code
            body = {
                "snapshot_id": SNAPSHOT_ID,
                "as_of": CLOCK,
                "source": "northstar:mcp",
                "error": {"code": code, "message": message},
            }
            return types.CallToolResult(
                content=[types.TextContent(text=json.dumps(body))],
                structured_content=body,
                is_error=True,
            )
        finally:
            LOGGER.info(
                json.dumps(
                    {
                        "event": "mcp_tool_call",
                        "tool": name if name in TOOL_SPECS else "unknown",
                        "request_id": request_id,
                        "outcome": outcome,
                        "snapshot_id": SNAPSHOT_ID,
                        "duration_ms": round((time.monotonic() - started) * 1000, 3),
                    }
                )
            )
