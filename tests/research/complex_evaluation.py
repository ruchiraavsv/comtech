"""Catalogue and HTTP harness for opt-in evaluations; never imports private answer keys."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from comtech.agents.contracts import SupervisorAnswerPackage
from comtech.agents.errors import ProviderQuotaExhausted


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1)
    require_claims: bool
    required_sources: list[str] = Field(default_factory=list)
    required_modes: list[Literal["semantic", "deterministic", "mixed"]] = Field(
        default_factory=list
    )
    require_computation: bool = False
    require_gap: bool = False
    require_clarification: bool = False
    forbidden_answer_text: list[str] = Field(default_factory=list)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^(KW|RS|RD|RM|XW|EDGE)\d{2}$")
    title: str
    category: Literal[
        "knowledge_worker", "semantic", "deterministic", "mixed", "cross_worker", "limitations"
    ]
    expected_route: str
    turns: list[Turn] = Field(min_length=1)
    review: list[str] = Field(min_length=1)
    fail_if: list[str] = Field(min_length=1)


class Catalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    suite_id: str
    document_release: str
    mcp_snapshot: str
    cases: list[Case]


def load_catalogue():
    catalogue = Catalogue.model_validate_json(
        Path(__file__).with_name("complex_cases.json").read_text(encoding="utf-8")
    )
    ids = [case.id for case in catalogue.cases]
    if len(ids) != 30 or len(set(ids)) != len(ids):
        raise ValueError("The complex evaluation requires 30 uniquely identified cases")
    return catalogue


def check_result(turn, state, result):
    """Structural checks only. A passing result still needs the case's semantic review."""
    assert state["status"] == "completed", f"Run ended as {state['status']}"
    assert result["review_status"] == "approved", "Answer did not pass Reviewer"
    assert result["answer"].strip(), "Empty final answer"
    package = SupervisorAnswerPackage.model_validate(result["answer_package"])
    evidence = result["evidence"]
    computations = set(result.get("research", {}).get("computation_refs", []))
    for claim in package.claims:
        assert set(claim.evidence_ids) <= evidence.keys(), "Missing selected evidence"
        assert claim.evidence_ids or claim.computation_ref, "Claim has no supporting references"
        if claim.computation_ref:
            assert claim.computation_ref in computations, "Unretained computation reference"
    if turn.require_claims:
        assert package.claims, "Expected supported factual claims"
    if turn.require_gap:
        assert package.unresolved or package.limitations or package.clarification, (
            "Expected an explicit information gap"
        )
    if turn.require_clarification:
        assert package.clarification, "Expected a clarifying question"
    sources = {e["source_ref"]["source_type"] for e in evidence.values()}
    assert set(turn.required_sources) <= sources, f"Missing sources: {turn.required_sources}"
    modes = {t["mode"] for t in state["progress"]["tasks"] if t["kind"] == "research"}
    assert set(turn.required_modes) <= modes, f"Missing Research modes: {turn.required_modes}"
    if turn.require_computation:
        assert computations and any(c.computation_ref for c in package.claims), (
            "Expected a selected computed claim"
        )
    for marker in turn.forbidden_answer_text:
        assert marker.casefold() not in result["answer"].casefold(), "Injected marker in answer"


async def save_report(path, report):
    def write():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    await asyncio.to_thread(write)


async def cancel_unfinished(client, thread_id, records):
    """The thread is newly created for this case, including any lost-acknowledgement run."""
    cleanup = []
    known = {r["run_id"] for r in records if r.get("run_id")}
    try:
        response = await client.get(f"/api/threads/{thread_id}/runs")
        response.raise_for_status()
        known.update(r["run_id"] for r in response.json())
    except Exception as error:
        cleanup.append({"discovery_error": type(error).__name__, "thread_id": thread_id})
    for run_id in sorted(known):
        try:
            response = await client.get(f"/api/runs/{run_id}")
            response.raise_for_status()
            if response.json()["status"] in ("completed", "failed", "cancelled"):
                continue
            response = await client.post(f"/api/runs/{run_id}/cancel")
            response.raise_for_status()
            cleanup.append({"run_id": run_id, "cancel_requested": True})
        except Exception as error:
            cleanup.append({"run_id": run_id, "cancel_error": type(error).__name__})
    return cleanup


async def evaluate_case(client, catalogue, case, directory, *, poll_seconds=2):
    thread_id = str(uuid4())
    path = Path(directory) / f"{case.id}-{thread_id}.json"
    report = {
        "schema_version": 1,
        "suite_id": catalogue.suite_id,
        "case": case.model_dump(mode="json"),
        "expected_sources": {
            "documents": catalogue.document_release,
            "northstar": catalogue.mcp_snapshot,
        },
        "started_at": datetime.now(UTC).isoformat(),
        "thread_id": thread_id,
        "automated_status": "running",
        "semantic_review": {
            "status": "pending",
            "reviewer": None,
            "checks": [{"criterion": text, "verdict": "pending"} for text in case.review],
            "failure_checks": [{"criterion": text, "verdict": "pending"} for text in case.fail_if],
        },
        "turns": [],
    }
    await save_report(path, report)
    try:
        health = await client.get("/health/ready")
        health.raise_for_status()
        assert health.json()["research_enabled"] and health.json()["background_enabled"]
        for index, turn in enumerate(case.turns, 1):
            record = {
                "turn": index,
                "prompt": turn.prompt,
                "idempotency_key": "complex-" + uuid4().hex,
                "automated_status": "running",
            }
            report["turns"].append(record)
            await save_report(path, report)
            started = monotonic()
            async with asyncio.timeout(1900):
                body = {
                    "thread_id": thread_id,
                    "message": turn.prompt,
                    "execution_mode": "background",
                    "idempotency_key": record["idempotency_key"],
                }
                # Retry only an ambiguous transport failure, with the exact same identity/body.
                for attempt in range(2):
                    try:
                        response = await client.post("/api/runs", json=body)
                        response.raise_for_status()
                        break
                    except httpx.TransportError:
                        if attempt:
                            raise
                run = response.json()
                record["run_id"] = run["run_id"]
                await save_report(path, report)
                while True:
                    response = await client.get(f"/api/runs/{run['run_id']}")
                    response.raise_for_status()
                    state = response.json()
                    record["state"] = state
                    if state["status"] in ("completed", "failed", "cancelled", "interrupted"):
                        break
                    await asyncio.sleep(poll_seconds)
                record["state"] = state
                result = await client.get(f"/api/runs/{run['run_id']}/result")
                record["result_http_status"] = result.status_code
                record["result"] = result.json()
                record["elapsed_seconds"] = round(monotonic() - started, 3)
                await save_report(path, report)
                if state.get("terminal_reason") == "ProviderQuotaExhausted":
                    raise ProviderQuotaExhausted(
                        "Provider quota exhausted; stop hosted evaluation."
                    )
                assert state["status"] == "completed", (
                    f"{case.id} turn {index}: {state['status']}; see {path}"
                )
                result.raise_for_status()
                pins = state["progress"]["source_versions"]
                assert pins["documents"] == catalogue.document_release, "Wrong document release"
                assert pins["northstar"] == catalogue.mcp_snapshot, "Wrong operational snapshot"
                check_result(turn, state, record["result"])
                record["automated_status"] = "passed"
                await save_report(path, report)
        report["automated_status"] = "passed"
    except BaseException as error:
        report["automated_status"] = "failed"
        report["error_type"] = type(error).__name__
        if isinstance(error, AssertionError):
            report["check_failure"] = str(error)[:1000]
        if report["turns"]:
            report["turns"][-1]["automated_status"] = "failed"
        report["cleanup"] = await cancel_unfinished(client, thread_id, report["turns"])
        raise
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        await save_report(path, report)
    return report
