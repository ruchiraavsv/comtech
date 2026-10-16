import hashlib
import json
import shutil

import pytest
from pydantic import ValidationError

from comtech.mcp.repository import SnapshotError, load_snapshot

from .conftest import FIXTURES


def test_story_paths_and_immutability(snapshot):
    assert snapshot.info()["counts"] == {
        "employees": 21,
        "teams": 8,
        "services": 10,
        "oncall_shifts": 20,
        "open_incidents": 3,
        "deployments": 10,
    }
    mc = snapshot.get("services", "merchantconnect")
    assert mc.owner_team_id == "payments-platform-reliability"
    assert mc.responsibilities[0].employee_id == "E1044"
    assert snapshot.get("services", "authhub").responsibilities[0].employee_id == "E4010"
    assert snapshot.shifts("settlementhub")[0].employee_id != "E2031"
    assert snapshot.deployment("merchantconnect").version == "4.7.2"
    assert snapshot.deployment("fraudshield").model_release_id == "MODEL-2026-04"
    with pytest.raises(TypeError):
        snapshot.tables["employees"]["E1043"] = None
    with pytest.raises(ValidationError):
        mc.responsibilities[0].employee_id = "E0990"


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("hash", "hash mismatch"),
        ("inactive", "Inactive or unknown responder"),
        ("overlap", "Shift gap/overlap"),
        ("owner", "Service relationship differs"),
        ("duplicate", "Duplicate record IDs"),
        ("future", "Future record update"),
    ],
)
def test_corrupted_snapshot_fails(tmp_path, mutation, reason):
    target = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, target)
    table = "services" if mutation == "owner" else "oncall_shifts"
    path = target / f"{table}.json"
    rows = json.loads(path.read_text())
    if mutation == "inactive":
        rows[0]["employee_id"] = "E0990"
    elif mutation == "overlap":
        rows[1]["starts_at"] = "2026-09-15T19:00:00Z"
    elif mutation == "owner":
        rows[0]["owner_team_id"] = "checkout-engineering"
    elif mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "future":
        rows[0]["updated_at"] = "2026-09-16T10:00:00Z"
    else:
        rows[0]["employee_id"] = "E2050"
    path.write_text(json.dumps(rows))
    if mutation != "hash":
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][table]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(SnapshotError, match=reason):
        load_snapshot(target)
