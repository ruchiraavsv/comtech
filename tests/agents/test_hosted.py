"""Explicit opt-in: paid model/embedding calls and hosted read-only search."""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from comtech.agents.runtime import enterprise_runtime
from comtech.mcp.server import create_app
from comtech.mcp.settings import MCPSettings
from comtech.settings import Settings
from tests.mcp.conftest import FIXTURES, serve

pytestmark = pytest.mark.hosted


@pytest.mark.parametrize(
    "kind,prompt,required",
    [
        ("operational", "Who owns MerchantConnect currently?", {"service_catalog"}),
        (
            "document",
            "What does the service ownership transfer policy say about the transfer date? "
            "Use documentary evidence only.",
            {"document"},
        ),
        (
            "mixed",
            "Who owns MerchantConnect currently, and who owned its original design in 2025? "
            "Distinguish the dates and authorities.",
            {"service_catalog", "document"},
        ),
    ],
)
async def test_real_models_and_sources(kind, prompt, required):
    if os.getenv("RUN_AGENT_HOSTED_TESTS") != "1":
        pytest.skip("Set RUN_AGENT_HOSTED_TESTS=1 for paid end-to-end checks")
    app = create_app(MCPSettings(fixture_directory=FIXTURES))
    async with serve(app) as url:
        settings = Settings(
            agent_mcp_url=url + "/mcp", agent_mode="enterprise", agent_model_timeout_seconds=60
        )
        async with enterprise_runtime(settings, InMemorySaver()) as graph:
            config = {"configurable": {"thread_id": str(uuid4())}, "recursion_limit": 200}
            async with asyncio.timeout(300):
                output = await graph.ainvoke({"messages": [HumanMessage(content=prompt)]}, config)
    found = {e["source_ref"]["source_type"] for e in output["evidence"].values()}
    assert required.issubset(found)
    if kind == "document":
        assert found == {"document"}
    assert output["review_decision"]["status"] == "approved"
    assert output["final_answer"] and "[1]" in output["final_answer"]
    report = Path("var/agents-validation")
    await asyncio.to_thread(report.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(
        (report / f"{kind}.json").write_text,
        json.dumps(
            {
                "source_types": sorted(found),
                "task_count": len(output["task_results"]),
                "review_cycles": output["review_cycle"],
                "approved": True,
                "worker_statuses": {
                    key: {
                        "status": result["status"],
                        "termination_reason": result["termination_reason"],
                    }
                    for key, result in output["task_results"].items()
                },
                "answer": output["final_answer"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
