"""Background HTTP client: idempotent submission and bounded event replay."""

from uuid import uuid4

from httpx_sse import connect_sse

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


def submission(thread_id, message, key=None):
    return {
        "thread_id": thread_id,
        "message": message,
        "execution_mode": "background",
        "idempotency_key": key or str(uuid4()),
    }


def submit(client, body):
    response = client.post("/api/runs", json=body)
    response.raise_for_status()
    return response.json()["run_id"]


def poll(client, run_id, cursor=0):
    path = f"/api/runs/{run_id}"
    response = client.get(path)
    response.raise_for_status()
    state = response.json()
    if state.get("result_expired"):
        return state, cursor, None
    # A finite replay returns promptly, so the UI can service cancellation between polls.
    with connect_sse(client, "GET", path + "/events", params={"after": cursor}) as source:
        source.response.raise_for_status()
        for item in source.iter_sse():
            if not item.data or not item.id:
                continue
            owner, sequence = item.id.rsplit(":", 1)
            if owner != run_id:
                raise ValueError("Event belongs to another run")
            cursor = max(cursor, int(sequence))
    # Only the committed, reviewed result is answer text. Event payloads are never rendered.
    answer = None
    if state.get("result_available"):
        result = client.get(path + "/result")
        result.raise_for_status()
        answer = result.json()["answer"]
    return state, cursor, answer
