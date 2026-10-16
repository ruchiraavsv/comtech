"""UI reconnect/reload/cancel checks with synthetic HTTP responses."""

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest


def test_background_reload_uses_saved_final_without_resubmission(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.syspath_prepend(str(Path("ui").resolve()))
    run, thread = str(uuid4()), str(uuid4())
    requests = []
    state = {
        "id": run,
        "thread_id": thread,
        "status": "completed",
        "message": "Original question",
        "execution_mode": "background",
        "result_available": True,
        "result_expired": False,
        "progress": {},
    }

    def handle(request):
        requests.append(request)
        if request.url.path == "/health/ready":
            value = {"mode": "enterprise", "background_enabled": True, "research_enabled": True}
        elif request.url.path.endswith("/runs"):
            value = [state]
        elif request.url.path.endswith("/events"):
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text="")
        elif request.url.path.endswith("/result"):
            value = {"answer": "Reviewed saved answer [1]"}
        else:
            value = state
        return httpx.Response(200, json=value)

    real = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: real(**kwargs, transport=httpx.MockTransport(handle))
    )
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kwargs: real(transport=httpx.MockTransport(handle)).get(url, **kwargs),
    )
    for _ in range(2):  # A fresh app instance represents a browser reload.
        app = AppTest.from_file(Path("ui/app.py").resolve())
        app.query_params.update(thread=thread, run=run, cursor="7")
        app.run()
        assert not app.exception
        assert any("Reviewed saved answer" in m.value for m in app.markdown)
        assert app.query_params["run"] == [run]
    assert not any(r.method == "POST" for r in requests)
    assert all(r.url.params["after"] == "7" for r in requests if r.url.path.endswith("/events"))


def test_background_client_idempotent_retry_cursor_and_final_gate(monkeypatch):
    monkeypatch.syspath_prepend(str(Path("ui").resolve()))
    from background import poll, submission, submit

    run, thread, calls = str(uuid4()), str(uuid4()), []

    def handle(request):
        calls.append(request)
        if request.method == "POST":
            if len(calls) == 1:
                raise httpx.ReadTimeout("Acknowledgement lost")
            return httpx.Response(202, json={"run_id": run})
        if request.url.path.endswith("/events"):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=(
                    f"id: {run}:5\ndata: "
                    '{"type":"TEXT_MESSAGE_CONTENT","delta":"Uncommitted"}\n\n'
                ),
            )
        return httpx.Response(200, json={"status": "running", "result_available": False})

    with httpx.Client(base_url="http://test", transport=httpx.MockTransport(handle)) as client:
        body = submission(thread, "Question")
        with pytest.raises(httpx.ReadTimeout):
            submit(client, body)
        assert submit(client, body) == run
        _, cursor, answer = poll(client, run, 4)
        assert cursor == 5 and answer is None
    assert json.loads(calls[0].content) == json.loads(calls[1].content)
