"""Validated, immutable snapshot storage. No database or client application imports."""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from pydantic import TypeAdapter

from .models import CLOCK, Deployment, Employee, Incident, Manifest, Record, Service, Shift, Team

TABLES = {
    "employees": (Employee, "employee_id", 21),
    "teams": (Team, "team_id", 8),
    "services": (Service, "service_id", 10),
    "oncall_shifts": (Shift, "shift_id", 20),
    "open_incidents": (Incident, "incident_id", 3),
    "deployments": (Deployment, "deployment_id", 10),
}
# Binding Appendix F relationships, independent of generator implementation.
SERVICE_CONTRACT = {
    "merchantconnect": ("payments", "payments-platform-reliability", 1, "psp-gateway"),
    "payflow": ("payments", "checkout-engineering", 1, "merchantconnect"),
    "settlementhub": ("payments", "settlement-platform", 1, "eventmesh"),
    "eventmesh": ("platform", "messaging-platform", 1, "datagateway"),
    "fraudshield": ("risk", "fraud-platform", 1, "payflow"),
    "authhub": ("identity", "identity-platform", 1, "datagateway"),
    "notifyhub": ("platform", "customer-communications", 2, "eventmesh"),
    "ledgercore": ("finance", "settlement-platform", 1, "settlementhub"),
    "psp-gateway": ("payments", "payments-platform-reliability", 1, "datagateway"),
    "datagateway": ("platform", "platform-reliability", 2, "authhub"),
}


class SnapshotError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SnapshotError(message)


@dataclass(frozen=True)
class Snapshot:
    tables: Mapping[str, Mapping[str, Record]]
    snapshot_id: str
    as_of: datetime
    horizon_start: datetime
    horizon_end: datetime
    digest: str

    def rows(self, table):
        return tuple(self.tables[table].values())

    def get(self, table, record_id):
        return self.tables[table].get(record_id)

    def shifts(self, service_id):
        return tuple(
            sorted(
                (s for s in self.rows("oncall_shifts") if s.service_id == service_id),
                key=lambda s: s.starts_at,
            )
        )

    def deployment(self, service_id):
        return next(d for d in self.rows("deployments") if d.service_id == service_id)

    def info(self):
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": CLOCK,
            "schema_version": 1,
            "snapshot_digest": self.digest,
            "counts": {key: len(rows) for key, rows in self.tables.items()},
        }


def load_snapshot(directory: Path) -> Snapshot:
    raw_manifest = (directory / "manifest.json").read_bytes()
    manifest = Manifest.model_validate_json(raw_manifest, strict=True)
    require(set(manifest.files) == set(TABLES), "Unexpected or missing fixture tables")
    as_of = datetime.fromisoformat(manifest.as_of.replace("Z", "+00:00"))
    require(
        manifest.horizon_start <= as_of < manifest.horizon_end, "Snapshot clock outside horizon"
    )
    tables = {}
    for table, (model, id_field, count) in TABLES.items():
        spec = manifest.files[table]
        require(spec.filename == f"{table}.json", f"Unexpected fixture filename: {table}")
        path = directory / spec.filename
        require(path.resolve().parent == directory.resolve(), "Fixture escapes its directory")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == spec.sha256, f"Fixture hash mismatch: {table}")
        rows = TypeAdapter(tuple[model, ...]).validate_json(raw, strict=True)
        require(len(rows) == spec.count == count, f"Incorrect record count: {table}")
        index = {getattr(row, id_field): row for row in rows}
        require(len(index) == len(rows), f"Duplicate record IDs: {table}")
        for row in rows:
            require(row.record_id == getattr(row, id_field), f"Record ID mismatch: {table}")
            require(row.updated_at <= as_of, f"Future record update: {row.record_id}")
        tables[table] = MappingProxyType(index)
    snapshot = Snapshot(
        MappingProxyType(tables),
        manifest.snapshot_id,
        as_of,
        manifest.horizon_start,
        manifest.horizon_end,
        hashlib.sha256(raw_manifest).hexdigest(),
    )
    validate_relationships(snapshot)
    return snapshot


def validate_relationships(snapshot):
    employees = snapshot.tables["employees"]
    teams = snapshot.tables["teams"]
    services = snapshot.tables["services"]
    require(sum(e.active for e in employees.values()) == 20, "Expected twenty active employees")
    require(set(services) == set(SERVICE_CONTRACT), "Service IDs differ from Appendix F")
    require(
        set(teams) == {s[1] for s in SERVICE_CONTRACT.values()}, "Team IDs differ from Appendix F"
    )
    for eid, name, team in (
        ("E1043", "Alice Chen", "payments-platform-reliability"),
        ("E1044", "Daniel Wong", "payments-platform-reliability"),
        ("E2031", "Priya Rao", "settlement-platform"),
        ("E2050", "Ravi Perera", "checkout-engineering"),
        ("E3042", "Maya Fernando", "fraud-platform"),
    ):
        person = employees.get(eid)
        require(
            person is not None and person.name == name and person.team_id == team and person.active,
            f"Named employee differs from brief: {eid}",
        )
    for employee in employees.values():
        require(employee.team_id in teams, f"Missing employee team: {employee.employee_id}")
        require(
            employee.manager_id is None or employee.manager_id in employees,
            f"Missing manager: {employee.employee_id}",
        )
        visited = {employee.employee_id}
        manager = employee.manager_id
        while manager is not None:
            require(manager not in visited, "Employee manager cycle")
            visited.add(manager)
            require(manager in employees and employees[manager].active, "Missing/inactive manager")
            manager = employees[manager].manager_id
    for team in teams.values():
        manager = employees.get(team.manager_employee_id)
        require(
            manager is not None and manager.active and manager.team_id == team.team_id,
            f"Invalid team manager: {team.team_id}",
        )
    for sid, service in services.items():
        domain, team, tier, dependency = SERVICE_CONTRACT[sid]
        require(
            (service.domain, service.owner_team_id, service.tier, service.dependencies)
            == (domain, team, tier, (dependency,)),
            f"Service relationship differs from brief: {sid}",
        )
        require(all(dep in services for dep in service.dependencies), "Missing dependency")
        for responsibility in service.responsibilities:
            require(
                responsibility.employee_id in employees
                and employees[responsibility.employee_id].active,
                f"Invalid responsibility contact: {sid}",
            )
        shifts = snapshot.shifts(sid)
        require(len(shifts) == 2, f"Expected two primary shifts: {sid}")
        require(
            shifts[0].starts_at == snapshot.horizon_start
            and shifts[-1].ends_at == snapshot.horizon_end,
            f"Incomplete fixture-horizon coverage: {sid}",
        )
        require(shifts[0].ends_at == shifts[1].starts_at, f"Shift gap/overlap: {sid}")
        require(shifts[0].employee_id != shifts[1].employee_id, f"Missing responder handoff: {sid}")
    for shift in snapshot.rows("oncall_shifts"):
        require(shift.service_id in services, "Shift references unknown service")
        require(
            shift.rotation_id == services[shift.service_id].oncall_rotation_id,
            "Shift rotation mismatch",
        )
        require(
            shift.employee_id in employees and employees[shift.employee_id].active,
            "Inactive or unknown responder",
        )
        require(shift.starts_at < shift.ends_at, "Invalid shift interval")
    alice_shift = snapshot.shifts("merchantconnect")[0]
    require(
        alice_shift.employee_id == "E1043"
        and alice_shift.starts_at.isoformat() == "2026-09-15T08:00:00+00:00"
        and alice_shift.ends_at.isoformat() == "2026-09-15T20:00:00+00:00",
        "Alice shift differs from brief",
    )
    require(
        snapshot.shifts("payflow")[0].employee_id == "E2050", "PayFlow responder differs from brief"
    )
    incidents = snapshot.tables["open_incidents"]
    contract = {
        "INC-LIVE-1042": ("merchantconnect", "SEV-1", "investigating", "E1043"),
        "INC-LIVE-1051": ("payflow", "SEV-2", "mitigating", "E2050"),
        "INC-LIVE-1054": ("settlementhub", "SEV-2", "monitoring", "E2031"),
    }
    require(set(incidents) == set(contract), "Live incident IDs differ from brief")
    for iid, incident in incidents.items():
        require(
            (
                incident.service_id,
                incident.severity,
                incident.status,
                incident.commander_employee_id,
            )
            == contract[iid],
            f"Live incident differs from brief: {iid}",
        )
        require(
            incident.started_at <= incident.updated_at <= snapshot.as_of,
            "Invalid incident chronology",
        )
        require(
            incident.commander_employee_id in employees
            and employees[incident.commander_employee_id].active,
            "Missing/inactive incident commander",
        )
    require(
        "outbound connection utilization 96%" in incidents["INC-LIVE-1042"].symptoms,
        "Missing pinned saturation observation",
    )
    deployments = snapshot.rows("deployments")
    require(
        {d.service_id for d in deployments} == set(services)
        and len({d.service_id for d in deployments}) == len(deployments),
        "Expected exactly one deployment per service",
    )
    for deployment in deployments:
        require(
            deployment.deployed_at <= deployment.updated_at,
            "Deployment update predates implementation",
        )
    require(
        snapshot.deployment("merchantconnect").version == "4.7.2",
        "MerchantConnect version differs from brief",
    )
    require(
        snapshot.deployment("fraudshield").model_release_id is not None,
        "Missing FraudShield model identity",
    )
