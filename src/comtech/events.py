"""Translate selected graph activity into the public AG-UI contract."""

import json

from ag_ui.core import (
    CustomEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)


def sse_record(run_id, sequence, payload):
    return {"id": f"{run_id}:{sequence}", "data": json.dumps(payload, separators=(",", ":"))}


async def graph_events(graph, inputs, config, run_id, thread_id):
    yield RunStartedEvent(thread_id=str(thread_id), run_id=str(run_id))
    message_id = str(run_id)
    async for part in graph.astream(
        inputs, config, stream_mode=["tasks", "custom", "updates"], version="v2", durability="sync"
    ):
        kind, data = part["type"], part["data"]
        if kind == "tasks":
            if "input" in data:
                yield StepStartedEvent(step_name=data["name"])
            elif not data.get("error"):
                yield StepFinishedEvent(step_name=data["name"])
        elif kind == "custom":
            if data.get("event") == "agent.activity":
                allowed = {
                    key: data[key]
                    for key in (
                        "stage",
                        "model",
                        "tool",
                        "cycle",
                        "context_tokens",
                        "outcome",
                        "status",
                        "termination_reason",
                        "input_tokens",
                        "output_tokens",
                    )
                    if key in data
                }
                yield CustomEvent(name="agent.activity", value=allowed)
            else:
                yield CustomEvent(name="mock.progress", value=data)
        elif kind == "updates" and ("mock_node" in data or "final_answer" in data):
            node = "final_answer" if "final_answer" in data else "mock_node"
            messages = (data[node] or {}).get("messages", [])
            if not messages:
                continue  # A bounded wording correction publishes no draft message.
            message = messages[-1]
            yield TextMessageStartEvent(message_id=message_id, role="assistant")
            yield TextMessageContentEvent(message_id=message_id, delta=message.content)
            yield TextMessageEndEvent(message_id=message_id)
    yield RunFinishedEvent(thread_id=str(thread_id), run_id=str(run_id))
