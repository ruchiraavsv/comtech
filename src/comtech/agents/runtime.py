"""Application lifetime wiring; external clients remain outside checkpoint state."""

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

from comtech.integrations.northstar import NorthstarClient
from comtech.retrieval.search import HybridSearch
from comtech.retrieval.store import SourceStore

from .budget import TokenCounter
from .contracts import Limits
from .graph import build_enterprise_graph
from .model import StructuredModel
from .tools import KnowledgeTools


@asynccontextmanager
async def enterprise_runtime(settings, checkpointer, *, pool=None, resources=None, queue=None):
    limits = Limits(
        **{
            key: getattr(settings, key)
            for key in (
                "max_sections_per_read",
                "max_tokens_per_section",
                "max_tokens_per_read",
                "knowledge_worker_max_cycles",
                "total_context_budget",
                "finalization_reserve",
                "max_review_cycles",
            )
        },
        max_tasks=settings.agent_max_tasks,
        parallel_workers=settings.agent_parallel_workers,
        tool_timeout_seconds=settings.agent_tool_timeout_seconds,
        worker_timeout_seconds=settings.agent_worker_timeout_seconds,
    )
    if settings.agent_model_context_window < limits.total_context_budget:
        raise ValueError("Configured model context is smaller than worker budget")
    counter = await asyncio.to_thread(TokenCounter, settings.agent_token_encoding)
    store = await asyncio.to_thread(
        SourceStore, settings.ingestion_artifact_root, settings.agent_build_id
    )
    async with AsyncExitStack() as stack:
        model = StructuredModel(settings, counter)
        stack.push_async_callback(model.close)
        search = HybridSearch(store, settings, model.client, counter)
        stack.push_async_callback(search.close)
        mcp = NorthstarClient(settings.agent_mcp_url, limits.tool_timeout_seconds)
        await mcp.discover()
        tools = KnowledgeTools(store, search, mcp, counter, limits)
        if not settings.research_enabled:
            yield build_enterprise_graph(model, tools, counter, limits, checkpointer)
            return
        from comtech.research.agent import ResearchAgent
        from comtech.research.remote import RemoteBroker, RemotePython
        from comtech.research.specialist import ResearchSpecialist

        from .supervisor import build_supervisor_graph

        if pool is None or resources is None or queue is None:
            raise ValueError("Research runtime requires the shared scheduler resources")
        broker = RemoteBroker(
            pool,
            resources,
            counter,
            limits,
            settings.research_broker_url,
            settings.research_service_token.get_secret_value(),
        )
        stack.push_async_callback(broker.close)
        await broker.ready(settings.agent_build_id)
        research = ResearchAgent(model, broker, RemotePython(broker), queue, checkpointer)
        specialist = ResearchSpecialist(research, store)
        graph = build_supervisor_graph(
            model, tools, counter, limits, checkpointer, research=specialist
        )
        graph.research_agent, graph.research_specialist = research, specialist
        graph.research_broker, graph.query_embedding = broker, search.embed_query
        yield graph
