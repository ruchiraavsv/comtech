"""Validate operational fixtures and their alignment with private canonical history."""

import hashlib
import json
from pathlib import Path

from comtech.mcp.repository import load_snapshot, require

ROOT = Path(__file__).resolve().parents[1]


def validate():
    directory = ROOT / "mcp/fixtures"
    snapshot = load_snapshot(directory)
    source_path = ROOT / "canonical/operational_snapshot.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    history_path = ROOT / "canonical/truth.json"
    history = json.loads(history_path.read_text(encoding="utf-8"))
    require(
        manifest["source_sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "Operational source hash mismatch",
    )
    require(
        source["history_sha256"] == hashlib.sha256(history_path.read_bytes()).hexdigest(),
        "Canonical history changed; regenerate fixtures",
    )
    for table, rows in source["tables"].items():
        require(
            rows == json.loads((directory / f"{table}.json").read_text(encoding="utf-8")),
            f"Fixture differs from source: {table}",
        )
    historical_services = {s["service_id"]: s["display_name"] for s in history["services"]}
    docs = {d["entity_id"]: d for d in history["documents"]}
    changes = {c["change_id"]: c for c in source["historical_changes"]}
    for service in snapshot.rows("services"):
        require(
            service.name == historical_services[service.service_id],
            "Service name conflicts with history",
        )
        for role in service.responsibilities:
            require(
                all(d.removeprefix("DOC-") in docs for d in role.basis_document_ids),
                "Unresolved responsibility basis",
            )
    for deployment in snapshot.rows("deployments"):
        change = changes[deployment.change_id]
        require(deployment.service_id == change["service_id"], "Deployment/change service mismatch")
        require(
            deployment.deployed_at.isoformat().replace("+00:00", "Z") == change["implemented_at"],
            "Deployment/change date mismatch",
        )
        if change["document_id"]:
            doc = docs[deployment.change_id]
            require(
                doc["published_at"][:10] == change["implemented_at"][:10],
                "Deployment contradicts historical release date",
            )
    report = {
        "passed": True,
        **snapshot.info(),
        "story_coverage": {
            "S1": "MerchantConnect symptoms, ownership, shift and employee joins",
            "S2": "MerchantConnect current deployment references CHG-153",
            "S3": "SettlementHub current incident and EventMesh dependency",
            "S4": "Document-only; no operational answer invented",
            "S5": "FraudShield deployment, model and configuration identities",
            "S6": "SEV-1 record and explicit capacity-approval contact",
            "S7": "AuthHub privileged-review control-owner reference",
            "S8": "No general regional health telemetry; empty incident query is bounded",
            "S9": "Three open incidents and incident/service/shift/person lookup paths",
            "S10": "Current owner differs from original design ownership in ARCH-001",
        },
        "permissions": "deferred",
        "client_integration": "deferred",
    }
    (ROOT / "mcp/validation_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
