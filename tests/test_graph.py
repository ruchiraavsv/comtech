from uuid import uuid4

import pytest
from ag_ui.core import CustomEvent, RunFinishedEvent, StepStartedEvent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from comtech.events import graph_events
from comtech.graph import build_graph
from comtech.integrations.smoke import require_local_target
from comtech.settings import Settings


async def test_progress_precedes_completed_node_and_state_keeps_turns():
    graph = build_graph(InMemorySaver(), delay=0.01)
    config = {"configurable": {"thread_id": str(uuid4())}}
    events = [
        event
        async for event in graph_events(
            graph, {"messages": [HumanMessage(content="hello")]}, config, uuid4(), uuid4()
        )
    ]
    assert any(isinstance(e, StepStartedEvent) for e in events)
    assert len([e for e in events if isinstance(e, CustomEvent)]) == 3
    assert isinstance(events[-1], RunFinishedEvent)
    result = await graph.ainvoke({"messages": [HumanMessage(content="again")]}, config)
    assert "turn 2" in result["messages"][-1].content


def test_local_smoke_cannot_target_hosted_index():
    settings = Settings(
        _env_file=None, pinecone_mode="local", pinecone_local_host="https://example.svc.pinecone.io"
    )
    with pytest.raises(ValueError, match="local emulator"):
        require_local_target(settings)


def test_production_rejects_emulator():
    with pytest.raises(ValueError, match="hosted Pinecone"):
        Settings(_env_file=None, app_env="production", pinecone_mode="local")
