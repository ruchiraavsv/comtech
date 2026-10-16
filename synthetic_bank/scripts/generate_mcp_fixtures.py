"""Build the frozen operational snapshot from authored choices and canonical history."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "DEMO-2026-09-15-A"
CLOCK = "2026-09-15T10:00:00Z"
UPDATED = "2026-09-15T08:00:00Z"

# service, domain, owner team, tier, dependency, primary, next shift
SERVICES = [
    (
        "merchantconnect",
        "payments",
        "payments-platform-reliability",
        1,
        "psp-gateway",
        "E1043",
        "E1051",
    ),
    ("payflow", "payments", "checkout-engineering", 1, "merchantconnect", "E2050", "E2052"),
    ("settlementhub", "payments", "settlement-platform", 1, "eventmesh", "E2032", "E2033"),
    ("eventmesh", "platform", "messaging-platform", 1, "datagateway", "E3011", "E3010"),
    ("fraudshield", "risk", "fraud-platform", 1, "payflow", "E3043", "E3042"),
    ("authhub", "identity", "identity-platform", 1, "datagateway", "E4011", "E4010"),
    ("notifyhub", "platform", "customer-communications", 2, "eventmesh", "E5011", "E5010"),
    ("ledgercore", "finance", "settlement-platform", 1, "settlementhub", "E2033", "E2032"),
    (
        "psp-gateway",
        "payments",
        "payments-platform-reliability",
        1,
        "datagateway",
        "E1051",
        "E1043",
    ),
    ("datagateway", "platform", "platform-reliability", 2, "authhub", "E6011", "E6012"),
]
TEAMS = [
    ("payments-platform-reliability", "Payments Platform Reliability", "E1044"),
    ("checkout-engineering", "Checkout Engineering", "E2051"),
    ("settlement-platform", "Settlement Platform", "E2031"),
    ("messaging-platform", "Messaging Platform", "E3010"),
    ("fraud-platform", "Fraud Platform", "E3042"),
    ("identity-platform", "Identity Platform", "E4010"),
    ("customer-communications", "Customer Communications", "E5010"),
    ("platform-reliability", "Platform Reliability", "E6010"),
]
PEOPLE = [
    ("E1043", "Alice Chen", 0, "Senior SRE"),
    ("E1044", "Daniel Wong", 0, "Payments Platform Reliability Manager"),
    ("E1051", "Leila Hassan", 0, "SRE"),
    ("E2050", "Ravi Perera", 1, "Senior Checkout Engineer"),
    ("E2051", "Nora Silva", 1, "Checkout Engineering Manager"),
    ("E2052", "Owen Park", 1, "Checkout Engineer"),
    ("E2031", "Priya Rao", 2, "Settlement Platform Manager"),
    ("E2032", "Amir Tan", 2, "Settlement Engineer"),
    ("E2033", "Elena Costa", 2, "Ledger Engineer"),
    ("E3010", "Jonas Lee", 3, "Messaging Platform Manager"),
    ("E3011", "Mina Patel", 3, "Messaging Engineer"),
    ("E3042", "Maya Fernando", 4, "Fraud Platform Manager"),
    ("E3043", "Theo Martins", 4, "Fraud Platform Engineer"),
    ("E4010", "Sara Iqbal", 5, "Identity Platform Manager"),
    ("E4011", "Lucas Tran", 5, "Identity Engineer"),
    ("E5010", "Asha Reed", 6, "Customer Communications Manager"),
    ("E5011", "Noah Lim", 6, "Notification Engineer"),
    ("E6010", "Iris Mensah", 7, "Platform Reliability Manager"),
    ("E6011", "Mateo Cruz", 7, "Platform SRE"),
    ("E6012", "Zara Khan", 7, "Platform SRE"),
]
# service, version, change, implementation date; change-only additions have no corpus slot.
DEPLOYMENTS = [
    ("merchantconnect", "4.7.2", "CHG-153", "2026-08-07"),
    ("payflow", "3.9.0", "CHG-178", "2026-08-26"),
    ("settlementhub", "2.8.1", "CHG-301", "2026-08-15"),
    ("eventmesh", "1.8.0", "CHG-127", "2026-06-01"),
    ("fraudshield", "5.2.1", "CHG-109", "2026-05-10"),
    ("authhub", "2.4.0", "CHG-302", "2026-08-12"),
    ("notifyhub", "1.6.2", "CHG-303", "2026-08-11"),
    ("ledgercore", "3.1.0", "CHG-304", "2026-08-14"),
    ("psp-gateway", "2.2.3", "CHG-305", "2026-08-17"),
    ("datagateway", "1.9.1", "CHG-306", "2026-08-18"),
]


def base(record_id, updated_at=UPDATED):
    return {"record_id": record_id, "snapshot_id": SNAPSHOT, "updated_at": updated_at}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def create_source(history):
    names = {s["service_id"]: s["display_name"] for s in history["services"]}
    docs = {d["entity_id"]: d for d in history["documents"]}
    tables = {
        name: []
        for name in (
            "employees",
            "teams",
            "services",
            "oncall_shifts",
            "open_incidents",
            "deployments",
        )
    }
    for team_id, name, manager in TEAMS:
        tables["teams"].append(
            {**base(team_id), "team_id": team_id, "name": name, "manager_employee_id": manager}
        )
    for eid, name, team_index, title in PEOPLE:
        team_id, _, manager = TEAMS[team_index]
        tables["employees"].append(
            {
                **base(eid),
                "employee_id": eid,
                "name": name,
                "team_id": team_id,
                "title": title,
                "email": name.lower().replace(" ", ".") + "@northstar.example",
                "manager_id": None if manager == eid else manager,
                "active": True,
            }
        )
    tables["employees"].append(
        {
            **base("E0990", "2026-06-30T17:00:00Z"),
            "employee_id": "E0990",
            "name": "Adrian Brooks",
            "team_id": "payments-platform-reliability",
            "title": "Former MerchantConnect Service Owner",
            "email": "adrian.brooks@northstar.example",
            "manager_id": "E1044",
            "active": False,
        }
    )
    for sid, domain, team_id, tier, dependency, primary, next_employee in SERVICES:
        responsibilities = []
        if sid == "merchantconnect":
            responsibilities.append(
                {
                    "responsibility_id": "capacity-change-approval-contact",
                    "employee_id": "E1044",
                    "description": "Contact for the material capacity-change approval "
                    "process; this record grants no approval.",
                    "basis_document_ids": ["DOC-POL-007-v2", "DOC-RB-010"],
                }
            )
        if sid == "authhub":
            responsibilities.append(
                {
                    "responsibility_id": "privileged-access-review-control-owner",
                    "employee_id": "E4010",
                    "description": "Current owner of the privileged-access review control; "
                    "closure evidence remains in the audit documents.",
                    "basis_document_ids": ["DOC-POL-013-v2", "DOC-RISK-009"],
                }
            )
        rotation = f"{sid}-primary"
        tables["services"].append(
            {
                **base(sid),
                "service_id": sid,
                "name": names[sid],
                "domain": domain,
                "owner_team_id": team_id,
                "tier": tier,
                "dependencies": [dependency],
                "oncall_rotation_id": rotation,
                "responsibilities": responsibilities,
            }
        )
        for number, employee, start, end in [
            (1, primary, "2026-09-15T08:00:00Z", "2026-09-15T20:00:00Z"),
            (2, next_employee, "2026-09-15T20:00:00Z", "2026-09-16T08:00:00Z"),
        ]:
            shift_id = f"SHIFT-{sid}-{number}"
            tables["oncall_shifts"].append(
                {
                    **base(shift_id),
                    "shift_id": shift_id,
                    "service_id": sid,
                    "rotation_id": rotation,
                    "employee_id": employee,
                    "level": "primary",
                    "starts_at": start,
                    "ends_at": end,
                }
            )
    for iid, sid, severity, status, symptoms, commander, started, updated in [
        (
            "INC-LIVE-1042",
            "merchantconnect",
            "SEV-1",
            "investigating",
            ["payment timeouts", "outbound connection utilization 96%"],
            "E1043",
            "09:30",
            "09:55",
        ),
        (
            "INC-LIVE-1051",
            "payflow",
            "SEV-2",
            "mitigating",
            ["checkout latency", "retry queue growing"],
            "E2050",
            "09:20",
            "09:50",
        ),
        (
            "INC-LIVE-1054",
            "settlementhub",
            "SEV-2",
            "monitoring",
            ["corporate report delivery delay"],
            "E2031",
            "08:45",
            "09:45",
        ),
    ]:
        tables["open_incidents"].append(
            {
                **base(iid, f"2026-09-15T{updated}:00Z"),
                "incident_id": iid,
                "service_id": sid,
                "severity": severity,
                "status": status,
                "symptoms": symptoms,
                "commander_employee_id": commander,
                "started_at": f"2026-09-15T{started}:00Z",
                "confirmed_root_cause": None,
            }
        )
    changes = []
    for sid, version, change, date in DEPLOYMENTS:
        if change in docs and docs[change]["published_at"][:10] != date:
            raise ValueError(f"Deployment conflicts with canonical change date: {change}")
        deployed = date + "T09:00:00Z"
        changes.append(
            {
                "change_id": change,
                "service_id": sid,
                "implemented_at": deployed,
                "document_id": "DOC-" + change if change in docs else None,
            }
        )
        tables["deployments"].append(
            {
                **base(f"DEP-{sid}", deployed),
                "deployment_id": f"DEP-{sid}",
                "service_id": sid,
                "version": version,
                "deployed_at": deployed,
                "change_id": change,
                "environment": "production",
                "model_release_id": "MODEL-2026-04" if sid == "fraudshield" else None,
                "configuration_version": "threshold-bounded-2026-05-10"
                if sid == "fraudshield"
                else None,
            }
        )
    return {
        "snapshot_id": SNAPSHOT,
        "as_of": CLOCK,
        "schema_version": 1,
        "horizon_start": "2026-09-15T08:00:00Z",
        "horizon_end": "2026-09-16T08:00:00Z",
        "private_do_not_index": True,
        "historical_changes": changes,
        "history_sha256": hashlib.sha256((ROOT / "canonical/truth.json").read_bytes()).hexdigest(),
        "tables": tables,
        "assumptions": [
            "Unspecified names, current versions, shift partners and "
            "incident start times are synthetic fixed choices.",
            "The inactive former owner retains their last directory "
            "team; this is not the 2025 design-team record.",
            "Root team managers have null manager_id; this dataset does not model executives.",
            "Daniel Wong is the designated capacity-approval "
            "contact, not an automatic approval decision.",
            "Sara Iqbal owns the privileged-review control associated with "
            "AuthHub; historical closure stays documentary.",
            "Deployments CHG-301 through CHG-306 are additional canonical "
            "change entities without new document slots.",
            "FraudShield application version, model identity and "
            "threshold configuration are distinct fields.",
            "Known next shifts do not advance the frozen as_of clock. "
            "No regional health telemetry is provided.",
        ],
    }


def main():
    history = json.loads((ROOT / "canonical/truth.json").read_text(encoding="utf-8"))
    source = create_source(history)
    source_path = ROOT / "canonical/operational_snapshot.json"
    write(source_path, source)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    target = ROOT / "mcp/fixtures"
    files = {}
    for name, rows in source["tables"].items():
        path = target / f"{name}.json"
        write(path, rows)
        files[name] = {
            "filename": path.name,
            "count": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    write(
        target / "manifest.json",
        {
            key: source[key]
            for key in ("snapshot_id", "as_of", "schema_version", "horizon_start", "horizon_end")
        }
        | {"files": files, "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()},
    )
    print("Generated frozen MCP fixtures:", {name: spec["count"] for name, spec in files.items()})


if __name__ == "__main__":
    main()
