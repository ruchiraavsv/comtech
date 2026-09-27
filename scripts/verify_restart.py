"""Opt-in destructive-to-active-run check against this project's local stack only.

Kills only the Compose API container and restarts this project's Postgres/API.
Does not remove volumes. Run while no other demo work is in progress.
"""

import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
from httpx_sse import connect_sse

ROOT = Path(__file__).resolve().parents[1]
ENGINE = os.getenv("CONTAINER_ENGINE", "podman")
if ENGINE not in {"podman", "docker"}:
    raise ValueError("Unsupported container engine")
COMPOSE = [ENGINE, "compose", "-f", "compose.yaml", "-f", "compose.dev.yaml"]


def command(args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def collect(client, method, path, **kwargs):
    with connect_sse(client, method, path, **kwargs) as source:
        source.response.raise_for_status()
        return [event.json() for event in source.iter_sse() if event.data]


with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
    thread = str(uuid4())
    api_id = command([*COMPOSE, "ps", "-q", "api"])
    db_id = command([*COMPOSE, "ps", "-q", "postgres"])
    if not api_id or not db_id or "\n" in api_id or "\n" in db_id:
        raise RuntimeError("Expected exactly one running API and database")
    with connect_sse(
        client, "POST", "/api/runs", json={"thread_id": thread, "message": "crash test"}
    ) as source:
        source.response.raise_for_status()
        run_id = source.response.headers["x-run-id"]
        for event in source.iter_sse():
            if event.data and event.json()["type"] == "CUSTOM":
                command([ENGINE, "kill", "--signal", "KILL", api_id])
                break
    command([ENGINE, "restart", db_id])
    command([ENGINE, "start", api_id])
    deadline = time.monotonic() + 60
    while True:
        try:
            client.get("/health/ready").raise_for_status()
            break
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "interrupted", run["status"]
    saved = collect(client, "GET", f"/api/runs/{run_id}/events")
    assert any(e["type"] == "CUSTOM" for e in saved)
    history = client.get(f"/api/threads/{thread}/checkpoints").json()
    checkpoint = next(item for item in history if item["next"] == ["mock_node"])
    resumed = collect(
        client,
        "POST",
        f"/api/runs/{run_id}/resume",
        json={"checkpoint_id": checkpoint["checkpoint_id"]},
    )
    assert resumed[-1]["type"] == "RUN_FINISHED"
    assert collect(client, "GET", f"/api/runs/{run_id}/events") == saved
    print("Hard API crash, Postgres restart, saved-event replay, and checkpoint resume passed.")
