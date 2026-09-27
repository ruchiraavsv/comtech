import os
from uuid import uuid4

import httpx
import streamlit as st
from httpx_sse import connect_sse

API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
st.set_page_config(page_title="Comtech assistant", layout="wide")
st.title("Assistant infrastructure demo")
st.caption("Mock graph · no LLM or retrieval calls · progress and history are persisted")
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid4())
    st.session_state.messages = []

with st.sidebar:
    thread = st.text_input("Conversation ID", value=st.session_state.thread_id)
    if st.button("Load conversation"):
        st.session_state.thread_id = thread
        st.session_state.messages = []
        st.rerun()
    if st.button("New conversation"):
        st.session_state.thread_id = str(uuid4())
        st.session_state.messages = []
        st.rerun()
    st.caption("Send /fail to exercise a traced mock failure.")
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{API}/api/threads/{st.session_state.thread_id}/runs")
            response.raise_for_status()
            runs = response.json()
        selected = st.selectbox(
            "Saved run", runs, format_func=lambda r: f"{r['status']} · {r['id']}"
        )
        replay_clicked = st.button("Replay saved events", disabled=not runs)
    except httpx.HTTPError:
        st.warning("Backend unavailable or conversation ID invalid.")
        selected, replay_clicked = None, False

chat, activity = st.columns([2, 1])
with chat:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    prompt = st.chat_input("Send a message to the mock graph")


def display_stream(method, path, body=None):
    answer = ""
    seen = set()
    terminal = False
    with chat, st.chat_message("assistant"):
        answer_slot = st.empty()
    with activity:
        st.subheader("Agent activity")
        status = st.status("Reading events", expanded=True)
    with httpx.Client(timeout=httpx.Timeout(90, connect=10)) as client:
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
