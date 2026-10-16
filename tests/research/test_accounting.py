import asyncio
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import HumanMessage
from openai import APIConnectionError

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import Decision, Limits
from comtech.agents.graph import build_enterprise_graph
from comtech.research import accounting
from comtech.research.budgets import BudgetProfile
from comtech.research.ledger import AccountingError, RunClosed
from comtech.retrieval.search import HybridSearch
from comtech.retrieval.store import SearchArgs
from comtech.settings import Settings
from tests.agents.helpers import FakeModel, FakeTools
from tests.retrieval.test_sources import make_release

from .helpers import accounting_context, graph_config

pytestmark = pytest.mark.integration


async def test_all_roles_charged_and_budget_stop_routes_to_llm_finalization(research_pool):
    base = BudgetProfile()
    profile = {"limits": {**base.limits, "data_requests": 0}, "final_reserve": base.final_reserve}
    ctx, run = await accounting_context(research_pool, profile)
    model, tools = FakeModel(), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits())
    with accounting.bind(ctx):
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Find owner")]},
            graph_config(ctx, run),
        )
    assert not tools.calls
    worker = result["task_results"]["task-0"]
    assert worker["termination_reason"] == "objective_budget" and worker["schema_version"] == 2
    assert worker["status"] == "partial"  # Comes from the scripted model, not accounting code.
    assert "inspected sections" in result["final_answer"] and result["review_cycle"] == 1
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["model_requests"]["used"] == 6
    assert counts["model_tokens"]["used"] == 180
    assert counts["specialist_calls"]["used"] == 1
    assert counts["data_requests"]["used"] == 0


async def test_parallel_worker_allocations_serialize_when_only_one_fits(research_pool):
    ctx, run = await accounting_context(research_pool)
    tools = FakeTools(delay=0.01)
    graph = build_enterprise_graph(
        FakeModel(tasks=2), tools, TokenCounter(), Limits(parallel_workers=2)
    )
    with accounting.bind(ctx):
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Owners?")]}, graph_config(ctx, run)
        )
    assert len(result["task_results"]) == 2 and tools.peak == 1
    assert (await ctx.ledger.counters(ctx.lease.objective_id))["specialist_calls"]["used"] == 2


async def test_protected_root_steps_allow_submission_review_repair_and_final_wording(research_pool):
    base = BudgetProfile()
    ctx, run = await accounting_context(
        research_pool,
        {"limits": {**base.limits, "supervisor_steps": 4}, "final_reserve": base.final_reserve},
    )

    class RepairOnce(FakeModel):
        async def generate(self, role, payload, schema, maximum):
            if role == "review":
                self.reject = not any(r == "review" for r, _, _ in self.calls)
            value, usage = await super().generate(role, payload, schema, maximum)
            if role == "synthesize":
                value = value.model_copy(
                    update={"limitations": ["No evidence was inspected before exploration closed."]}
                )
            return value, usage

    model, tools = RepairOnce(tasks=0), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits())
    with accounting.bind(ctx):
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Assess existing evidence")]}, graph_config(ctx, run)
        )
    assert result["exploration_closed"] and result["review_cycle"] == 2
    assert not tools.calls
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["supervisor_steps"]["used"] == 2
    assert counts["model_requests"]["used"] == 5
    assert counts["model_tokens"]["used"] == 150


async def test_model_retries_count_each_attempt_and_keep_unknown_tokens_reserved(research_pool):
    ctx, _ = await accounting_context(research_pool)

    class Flaky(FakeModel):
        attempts = 0

        async def generate(self, *args):
            self.attempts += 1
            raise APIConnectionError(request=httpx.Request("POST", "https://synthetic.invalid"))

    model = Flaky()
    with accounting.bind(ctx), pytest.raises(AccountingError, match="retry limit"):
        await accounting.generate(model, "decision", {"task": {}}, Decision, 1000)
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert model.attempts == 2 and counts["model_requests"]["used"] == 2
    assert counts["retries"]["used"] == 1
    assert counts["model_tokens"]["reserved"] > 0 and counts["model_tokens"]["used"] == 0


async def test_invalid_model_output_replays_feedback_without_another_paid_call(research_pool):
    from comtech.agents.errors import InvalidModelOutput

    ctx, _ = await accounting_context(research_pool)

    class Malformed(FakeModel):
        attempts = 0

        async def generate(self, *args):
            self.attempts += 1
            raise InvalidModelOutput("Invalid JSON")

    model = Malformed()
    with accounting.bind(ctx):
        for _ in range(2):
            with pytest.raises(InvalidModelOutput, match="Invalid JSON"):
                await accounting.generate(model, "decision", {"task": {}}, Decision, 1000)
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert model.attempts == counts["model_requests"]["used"] == 1
    assert counts["model_tokens"]["reserved"] > 0
    assert counts["retries"]["used"] == 0


async def test_recovered_malformed_worker_does_not_block_the_next_worker(research_pool):
    from comtech.agents.errors import InvalidModelOutput

    ctx, run = await accounting_context(research_pool)

    class MalformedOnce(FakeModel):
        failed = False

        async def generate(self, role, payload, schema, maximum):
            if role == "decision" and not self.failed:
                self.failed = True
                raise InvalidModelOutput("Invalid JSON")
            return await super().generate(role, payload, schema, maximum)

    model, tools = MalformedOnce(tasks=2, decisions=2), FakeTools()
    graph = build_enterprise_graph(model, tools, TokenCounter(), Limits())
    with accounting.bind(ctx):
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Compare both services")]}, graph_config(ctx, run)
        )
    assert set(result["task_results"]) == {"task-0", "task-1"}
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["specialist_calls"]["used"] == 2
    assert counts["model_tokens"]["reserved"] > 0  # Unknown first-call usage is still charged.
    assert counts["model_tokens"]["protected"] <= BudgetProfile().final_reserve["model_tokens"]


async def test_caller_cancel_retains_resource_until_underlying_call_settles(research_pool):
    ctx, _ = await accounting_context(research_pool)
    ctx.resources.gates["source"] = asyncio.Semaphore(1)
    entered, release, second = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def slow():
        entered.set()
        await release.wait()
        return "first"

    async def next_call():
        second.set()
        return "second"

    with accounting.bind(ctx):
        first = asyncio.create_task(accounting.source_call(slow))
        await entered.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        later = asyncio.create_task(accounting.source_call(next_call))
        await asyncio.sleep(0.02)
        assert not second.is_set() and ctx.resources.inflight
        release.set()
        assert await later == "second"
        await ctx.resources.drain()
    assert (await ctx.ledger.counters(ctx.lease.objective_id))["source_requests"]["used"] == 2


async def test_late_output_is_discarded_but_usage_is_settled(research_pool):
    ctx, _ = await accounting_context(research_pool)

    async def cancel_during_call():
        async with research_pool.connection() as conn:
            await conn.execute(
                "UPDATE research_objectives SET cancel_requested_at=now() WHERE id=%s",
                (ctx.lease.objective_id,),
            )
        return "must not become evidence"

    with accounting.bind(ctx), pytest.raises(RunClosed):
        await accounting.source_call(cancel_during_call)
    assert (await ctx.ledger.counters(ctx.lease.objective_id))["source_requests"]["used"] == 1


async def test_hybrid_search_accounts_logical_delivery_embedding_and_each_branch(
    research_pool, tmp_path
):
    ctx, _ = await accounting_context(research_pool)
    store = make_release(tmp_path, ["A synthetic policy fact."])

    class Embeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
                usage=SimpleNamespace(total_tokens=3),
            )

    def handle(request):
        return httpx.Response(200, json={"matches": [{"_id": "DOC-0:v1:s0:p1"}]})

    search = HybridSearch(
        store,
        Settings(_env_file=None, pinecone_api_key="test"),
        SimpleNamespace(embeddings=Embeddings()),
        TokenCounter(),
        httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    try:
        with accounting.bind(ctx):
            for _ in range(2):
                await accounting.data_call(
                    "knowledge_search", {}, lambda: search.search(SearchArgs(query="policy"))
                )
    finally:
        await search.close()
    counts = await ctx.ledger.counters(ctx.lease.objective_id)
    assert counts["data_requests"]["used"] == 2
    assert counts["source_requests"]["used"] == 4
    assert counts["embedding_requests"]["used"] == 2
    assert counts["embedding_tokens"]["used"] == 6
    assert counts["rows"]["used"] == 2 and counts["documents_discovered"]["used"] == 1
    assert counts["bytes"]["used"] > 0
