"""Opt-in local HTTP smoke: graph traces, failures, sessions and read-only replay.

Start scripts/observability.cmd first. Creates synthetic runs in the local app.
"""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx


def spans(client, trace_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(
            "http://127.0.0.1:6006/v1/projects/comtech-local/spans",
            params={"trace_id": trace_id},
        )
        if response.status_code == 200:
            result = response.json()["data"]
            if any(s["name"] == "conversation_execution" for s in result):
                return result
        time.sleep(0.2)
    raise AssertionError(f"Trace {trace_id} did not arrive in Phoenix")


def verify_saved(client, saved):
    for run in saved:
        response = client.get(f"http://127.0.0.1:8000/api/runs/{run['id']}")
        response.raise_for_status()
        assert response.json()["otel_trace_id"] == run["otel_trace_id"]
        found = spans(client, run["otel_trace_id"])
        root = next(s for s in found if s["name"] == "conversation_execution")
        assert root["attributes"]["metadata.run_id"] == run["id"]
        assert root["attributes"]["session.id"] == run["thread_id"]
        assert root["attributes"]["execution.status"] == run["status"]
        assert root["status_code"] == ("OK" if run["status"] == "completed" else "ERROR")
        node = next(s for s in found if s["name"] == "mock_node")
        assert node["parent_id"] in {s["context"]["span_id"] for s in found}
        assert "input.value" in node["attributes"]
        records = [
            json.loads(line)
            for file in Path("var/logs").glob("api.jsonl*")
            for line in file.read_text(encoding="utf-8").splitlines()
        ]
        assert any(
            r.get("run_id") == run["id"] and r.get("otel_trace_id") == run["otel_trace_id"]
            for r in records
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-saved", action="store_true", help="Check after container recreation"
    )
    args = parser.parse_args()
    evidence = Path("var/observability-runs.json")
    with httpx.Client(trust_env=False, timeout=20) as client:
        if args.verify_saved:
            saved = json.loads(evidence.read_text())
        else:
            saved = []
            thread = str(uuid4())
            for message in ("Local observability smoke", "Second turn", "/fail"):
                response = client.post(
                    "http://127.0.0.1:8000/api/runs",
                    json={"thread_id": thread, "message": message},
                )
                response.raise_for_status()
                run_id = response.headers["x-run-id"]
                run = client.get(f"http://127.0.0.1:8000/api/runs/{run_id}").json()
                assert run["status"] == ("failed" if message == "/fail" else "completed")
                saved.append(run)
                before = spans(client, run["otel_trace_id"])
                playback = client.get(f"http://127.0.0.1:8000/api/runs/{run_id}/events")
                playback.raise_for_status()

                def events(text):
                    return [
                        json.loads(line[5:])
                        for line in text.splitlines()
                        if line.startswith("data:")
                    ]

                assert events(playback.text) == events(response.text)
                assert spans(client, run["otel_trace_id"]) == before
            traces = client.get(
                "http://127.0.0.1:6006/v1/projects/comtech-local/traces",
                params={"session_identifier": thread},
            )
            traces.raise_for_status()
            assert len(traces.json()["data"]) == 3
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(json.dumps(saved, indent=2))
        verify_saved(client, saved)
    print(f"Verified {len(saved)} persisted runs, nested Phoenix spans and correlated local logs.")


if __name__ == "__main__":
    main()
