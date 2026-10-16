from types import SimpleNamespace
from unittest.mock import AsyncMock

from comtech.agents.budget import TokenCounter
from comtech.research import accounting
from comtech.research.actions import ResearchLimits
from comtech.research.agent import ResearchAgent
from comtech.research.result_registry import ResultRegistry

from .test_evidence import computation_fixture


async def test_context_pruning_keeps_registered_computation_available(monkeypatch):
    registry, _ = computation_fixture()
    agent = object.__new__(ResearchAgent)
    agent.counter = TokenCounter()
    agent.limits = ResearchLimits()
    agent.registry = ResultRegistry(SimpleNamespace(capabilities=SimpleNamespace(pool=None)))
    agent.payload = AsyncMock(
        return_value=(
            {
                "last_result": {"large": "tool output"},
                "evidence": {"EV-source": registry.evidence["EV-source"].model_dump(mode="json")},
                "artifacts": {
                    "artifact": {"manifest": registry.artifacts["artifact"].model_dump(mode="json")}
                },
                "child_claims": {},
            },
            registry,
        )
    )
    agent.model = SimpleNamespace(
        context_window=30000,
        input_size=lambda role, p, schema: (
            30000 if any(p[k] for k in ("last_result", "evidence", "artifacts")) else 1000
        ),
    )
    agent.access = lambda state: SimpleNamespace(
        context=SimpleNamespace(
            ledger=SimpleNamespace(check=AsyncMock()),
            lease="lease",
        )
    )

    async def generate(model, role, payload, schema, maximum, **kwargs):
        assert role == "research_finalize" and kwargs["final"]
        assert not payload["last_result"] and not payload["evidence"] and not payload["artifacts"]
        manifest = payload["artifact_manifest"]["artifact"]
        assert manifest["result"] == "4" and manifest["execution_verified"]
        assert not manifest["coverage"]["population_complete"]
        assert maximum == agent.limits.final_output_tokens
        return schema.model_validate(
            {
                "status": "answered",
                "claims": [
                    {
                        "claim_id": "computed",
                        "statement": "Twice the value is 4.",
                        "support": "derived",
                        "evidence": [],
                        "computation_ref": "artifact",
                        "derivation": "Multiply by two.",
                    }
                ],
                "unresolved": [],
            }
        ), {}

    monkeypatch.setattr(accounting, "generate", generate)
    command = await agent.finalize({"task_id": "root", "reason": "context_budget", "failures": []})
    assert command.update["result"]["artifact_refs"] == ["artifact"]
    assert command.update["result"]["result"]["claims"][0]["computation_ref"] == "artifact"
