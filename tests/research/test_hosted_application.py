"""Explicit opt-in acceptance against an already configured Research stack.

This suite makes paid calls through that API and transmits retrieved document text.
It never starts/deploys services or changes sources. Human quality review is separate.
"""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

pytestmark = [
    pytest.mark.hosted,
    pytest.mark.skipif(
        os.getenv("RUN_HOSTED_RESEARCH") != "1", reason="Hosted Research requires explicit opt-in"
    ),
]

CASES = [
    (
        "ordinary",
        "Find one published document describing service ownership. "
        "Report one explicitly supported ownership fact with its citation.",
    ),
    (
        "semantic",
        "Use Research to compare how two published documents describe operational "
        "responsibilities. Report supported similarities, differences and any uncertainty. "
        "Stop once these two documents answer the comparison.",
    ),
    (
        "deterministic",
        "Use Research to count documents in the pinned Documents release grouped "
        "by document_type. Use exact metadata enumeration and Python, "
        "deduplicate document versions, "
        "and cite the computation. Do not infer counts from top-k search.",
    ),
    (
        "mixed",
        "Use Research to inspect at most three operational documents, classify whether each "
        "explicitly describes an escalation responsibility, and use Python to count those labels. "
        "Keep unknown separate from no, retain supporting citations, and limit the conclusion "
        "to the inspected documents.",
    ),
]


@pytest.mark.parametrize("expected_mode,question", CASES)
async def test_hosted_research(expected_mode, question):
    base = os.environ["HOSTED_RESEARCH_API_URL"].rstrip("/")
    directory = Path(os.environ.get("HOSTED_RESEARCH_REPORT_DIR", "var/research-evaluation"))
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        health = await client.get("/health/ready")
        health.raise_for_status()
        assert health.json()["research_enabled"]
        response = await client.post(
            "/api/runs",
            json={
                "thread_id": str(uuid4()),
                "message": question,
                "execution_mode": "background",
                "idempotency_key": "r6-evaluation-" + uuid4().hex,
            },
        )
        response.raise_for_status()
        run = response.json()
        try:
            async with asyncio.timeout(1900):
                while True:
                    response = await client.get(f"/api/runs/{run['run_id']}")
                    response.raise_for_status()
                    state = response.json()
                    if state["status"] in ("completed", "failed", "cancelled"):
                        break
                    await asyncio.sleep(2)
            result = await client.get(run["result_url"])
            report = {
                "expected_mode": expected_mode,
                "question": question,
                "state": state,
                "result": result.json(),
                "human_semantic_review": "pending",
            }
            (directory / f"{expected_mode}-{run['run_id']}.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            assert state["status"] == "completed", state
            result.raise_for_status()
            assert result.json()["review_status"] == "approved"
            assert result.json()["answer_package"]["claims"]
            modes = {
                task["mode"] for task in state["progress"]["tasks"] if task["kind"] == "research"
            }
            assert (not modes) if expected_mode == "ordinary" else expected_mode in modes
            if expected_mode in ("deterministic", "mixed"):
                assert result.json()["research"]["computation_refs"]
        except BaseException:
            # Interrupting evaluation must not leave a paid background objective running.
            await client.post(f"/api/runs/{run['run_id']}/cancel")
            raise
