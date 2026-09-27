import asyncio
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def build_graph(checkpointer, delay=0.4):
    async def mock_node(state: State):
        writer = get_stream_writer()
        for step in range(1, 4):
            writer({"completed": step - 1, "total": 3, "message": f"Mock step {step}/3"})
            await asyncio.sleep(delay)
        if state["messages"][-1].content == "/fail":
            raise ValueError("Deliberate mock failure")
        turns = sum(message.type == "human" for message in state["messages"])
        return {
            "messages": [AIMessage(content=f"Mock response for turn {turns}. No model was called.")]
        }

    return (
        StateGraph(State)
        .add_node("mock_node", mock_node)
        .add_edge(START, "mock_node")
        .add_edge("mock_node", END)
        .compile(checkpointer=checkpointer)
    )
