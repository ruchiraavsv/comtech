import os
from uuid import uuid4

import httpx
import streamlit as st
from background import TERMINAL, poll, submission, submit
from httpx_sse import connect_sse

API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
st.set_page_config(page_title="Comtech assistant", layout="wide")
st.title("Enterprise knowledge assistant")
try:
    health = httpx.get(f"{API}/health/ready", timeout=5)
    health.raise_for_status()
    features = health.json()
    mode = features.get("mode", "unknown")
except (httpx.HTTPError, ValueError):
    mode = "unknown"
    features = {}
st.caption(f"Mode: {mode} · progress and history are persisted")
if "thread_id" not in st.session_state:
    st.session_state.thread_id = st.query_params.get("thread", str(uuid4()))
    st.session_state.messages = []
st.query_params["thread"] = st.session_state.thread_id

with st.sidebar:
    thread = st.text_input("Conversation ID", value=st.session_state.thread_id)
    if st.button("Load conversation"):
        st.session_state.thread_id = thread
        st.session_state.messages = []
        st.query_params.clear()
        st.session_state.pop("pending_submission", None)
        st.rerun()
    if st.button("New conversation"):
        st.session_state.thread_id = str(uuid4())
        st.session_state.messages = []
        st.query_params.clear()
        st.session_state.pop("pending_submission", None)
        st.rerun()
    if mode == "mock":
        st.caption("Send /fail to exercise a traced mock failure.")
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{API}/api/threads/{st.session_state.thread_id}/runs")
            response.raise_for_status()
            runs = response.json()
        selected = st.selectbox(
            "Saved run", runs, format_func=lambda r: f"{r['status']} · {r['id']}"
        )
        replay_clicked = st.button("Open saved run", disabled=not runs)
    except httpx.HTTPError:
        st.warning("Backend unavailable or conversation ID invalid.")
        selected, replay_clicked = None, False
        runs = []

background = features.get("background_enabled", False) or bool(st.query_params.get("run"))
if background:
    active = next((r for r in runs if r["status"] not in TERMINAL), None)
    if replay_clicked and selected:
        st.query_params["run"] = selected["id"]
        st.query_params["cursor"] = "0"
    elif active and not st.query_params.get("run"):
        st.query_params["run"] = active["id"]
    if st.session_state.get("pending_submission"):
        st.warning("Submission is awaiting acknowledgement. Retry uses the same request ID.")
        if st.button("Retry submission"):
            try:
                with httpx.Client(base_url=API, timeout=10) as client:
                    st.query_params["run"] = submit(client, st.session_state.pending_submission)
                st.session_state.pop("pending_submission")
                st.query_params.pop("submission", None)
                st.query_params["cursor"] = "0"
                st.rerun()
            except httpx.HTTPError:
                st.error("Could not confirm submission. Saved runs remain available.")

    @st.fragment(run_every="2s")
    def background_run():
        run_id = st.query_params.get("run")
        if not run_id:
            return
        try:
            cursor = max(0, int(st.query_params.get("cursor", "0")))
            with httpx.Client(base_url=API, timeout=10) as client:
                state, cursor, answer = poll(client, run_id, cursor)
                st.query_params["cursor"] = str(cursor)
                if active and active["id"] == run_id and state["status"] in TERMINAL:
                    st.rerun()
                if state.get("message"):
                    with st.chat_message("user"):
                        st.write(state["message"])
                st.caption("Status: " + state["status"])
                if state["status"] not in TERMINAL and st.button("Cancel research", key=run_id):
                    reply = client.post(f"/api/runs/{run_id}/cancel")
                    reply.raise_for_status()
                    st.rerun()
                if state.get("result_expired"):
                    st.info("The saved output has expired.")
                elif answer:
                    with st.chat_message("assistant"):
                        st.write(answer)
                elif state["status"] in {"failed", "cancelled", "interrupted"}:
                    st.info("This run ended without a reviewed answer.")
                progress = state.get("progress", {})
                if progress.get("tasks"):
                    with st.expander("Progress"):
                        for task in progress["tasks"]:
                            label = task.get("mode") or task["kind"]
                            st.write(f"{label}: {task['state']} ({task['count']})")
                        usage = progress.get("usage", {})
                        st.caption(
                            "Model tokens used: "
                            + str(usage.get("model_tokens", {}).get("used", 0))
                        )
        except (httpx.HTTPError, ValueError):
            st.warning("Connection interrupted. This view will reconnect to the same run.")

    background_run()
    prompt = st.chat_input(
        "Ask about enterprise documents or operational records",
        disabled=bool(active or st.session_state.get("pending_submission")),
    )
    if prompt:
        key = st.query_params.get("submission") or str(uuid4())
        st.query_params["submission"] = key
        st.session_state.pending_submission = submission(st.session_state.thread_id, prompt, key)
        try:
            with httpx.Client(base_url=API, timeout=10) as client:
                st.query_params["run"] = submit(client, st.session_state.pending_submission)
            st.session_state.pop("pending_submission")
            st.query_params.pop("submission", None)
            st.query_params["cursor"] = "0"
        except httpx.HTTPError:
            pass  # Preserve the exact request for an idempotent retry.
        st.rerun()
    st.stop()

chat, activity = st.columns([2, 1])
with chat:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    prompt = st.chat_input("Ask about enterprise documents or operational records")


def display_stream(method, path, body=None):
    answer = ""
    seen = set()
    terminal = False
    with chat, st.chat_message("assistant"):
        answer_slot = st.empty()
    with activity:
        st.subheader("Agent activity")
        status = st.status("Reading events", expanded=True)
    with httpx.Client(timeout=httpx.Timeout(330, connect=10)) as client:
        with connect_sse(client, method, API + path, json=body) as source:
            source.response.raise_for_status()
            for item in source.iter_sse():
                if not item.data or item.id in seen:
                    continue
                seen.add(item.id)
                event = item.json()
                kind = event["type"]
                if kind == "TEXT_MESSAGE_CONTENT":
                    answer += event["delta"]
                    answer_slot.write(answer)
                elif kind == "RUN_ERROR":
                    status.update(label=event["message"], state="error")
                    terminal = True
                elif kind == "RUN_FINISHED":
                    status.update(label="Completed", state="complete")
                    terminal = True
                else:
                    status.write(event.get("value", event.get("stepName", kind)))
    if not terminal:
        status.update(
            label="Recorded stream ended without completion; inspect run status", state="error"
        )
    return answer


try:
    if prompt:
        with chat, st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        answer = display_stream(
            "POST",
            "/api/runs",
            {
                "thread_id": st.session_state.thread_id,
                "message": prompt,
            },
        )
        if answer:
            st.session_state.messages.append({"role": "assistant", "content": answer})
    elif replay_clicked and selected:
        display_stream("GET", f"/api/runs/{selected['id']}/events")
except httpx.HTTPError:
    st.error("The API connection failed. Saved runs remain available for replay.")
