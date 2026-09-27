import argparse
import asyncio
from urllib.parse import urlparse
from uuid import uuid4

from pinecone import PineconeAsyncio

from comtech.settings import Settings


def require_local_target(settings):
    host = urlparse(settings.pinecone_local_host)
    if (
        settings.pinecone_mode != "local"
        or host.scheme != "http"
        or host.hostname not in {"localhost", "127.0.0.1", "pinecone-local"}
    ):
        raise ValueError("Local tests require an explicit local emulator target")


async def local(settings):
    require_local_target(settings)
    namespace = f"test-{uuid4()}"
    other = f"{namespace}-other"
    async with PineconeAsyncio(api_key="local-test") as pc:
        async with pc.IndexAsyncio(host=settings.pinecone_local_host) as index:
            for attempt in range(30):
                try:
                    await index.describe_index_stats()
                    break
                except Exception:
                    if attempt == 29:
                        raise
                    await asyncio.sleep(1)
            try:
                await index.upsert(
                    namespace=namespace,
                    vectors=[
                        {"id": "public", "values": [1, 0, 0], "metadata": {"access": "public"}},
                        {"id": "internal", "values": [0, 1, 0], "metadata": {"access": "internal"}},
                    ],
                )
                await index.upsert(namespace=other, vectors=[{"id": "other", "values": [1, 0, 0]}])
                result = await index.query(
                    namespace=namespace,
                    vector=[1, 0, 0],
                    top_k=3,
                    filter={"access": {"$eq": "public"}},
                    include_metadata=True,
                )
                assert [m.id for m in result.matches] == ["public"]
                result = await index.query(namespace=other, vector=[1, 0, 0], top_k=3)
                assert [m.id for m in result.matches] == ["other"]
            finally:
                await index.delete(namespace=namespace, delete_all=True)
                await index.delete(namespace=other, delete_all=True)
    print("Pinecone Local: upsert, query, filtering, namespace isolation, and cleanup passed.")


async def main(provider):
    settings = Settings()
    if provider == "pinecone-local":
        await local(settings)
    elif provider == "pinecone-hosted":
        if settings.pinecone_mode != "hosted" or not settings.pinecone_api_key.get_secret_value():
            raise ValueError("Hosted Pinecone mode and key are required")
        async with PineconeAsyncio(api_key=settings.pinecone_api_key.get_secret_value()) as pc:
            indexes = await pc.list_indexes()
            print(f"Hosted Pinecone authentication passed ({len(indexes.indexes)} indexes).")
    elif provider == "openai":
        from openai import AsyncOpenAI

        if not settings.openai_api_key.get_secret_value():
            raise ValueError("OPENAI_API_KEY is required")
        async with AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(), timeout=10, max_retries=1
        ) as client:
            await client.models.list()
        print("OpenAI authentication passed; no generation or embedding call was made.")
    elif provider == "langsmith":
        from langchain_core.messages import HumanMessage
        from langgraph.checkpoint.memory import InMemorySaver
        from langsmith import Client, tracing_context

        from comtech.graph import build_graph

        if not settings.langsmith_tracing:
            raise ValueError("Enable LANGSMITH_TRACING and set its API key")
        client = Client(
            api_key=settings.langsmith_api_key.get_secret_value(),
            api_url=settings.langsmith_endpoint,
            workspace_id=settings.langsmith_workspace_id or None,
        )
        graph = build_graph(InMemorySaver(), delay=0)
        thread = str(uuid4())
        traces = []
        try:
            with tracing_context(
                enabled=True, client=client, project_name=settings.langsmith_project
            ):
                for message in ("first", "second", "/fail"):
                    run_id = uuid4()
                    traces.append(run_id)
                    try:
                        await graph.ainvoke(
                            {"messages": [HumanMessage(content=message)]},
                            {
                                "configurable": {"thread_id": thread},
                                "run_id": run_id,
                                "metadata": {"thread_id": thread},
                                "tags": ["smoke-test"],
                            },
                        )
                    except ValueError:
                        if message != "/fail":
                            raise
            await asyncio.to_thread(client.flush)
            for run_id in traces:
                # Ingestion is asynchronous; tolerate bounded propagation delay.
                for attempt in range(15):
                    try:
                        trace = await asyncio.to_thread(client.read_run, run_id)
                        if trace.end_time is None:
                            raise RuntimeError("Trace not finalized")
                        break
                    except Exception:
                        if attempt == 14:
                            raise
                        await asyncio.sleep(1)
                print(f"Verified LangSmith trace {run_id}; error={bool(trace.error)}")
        finally:
            await asyncio.to_thread(client.close)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "provider", choices=["pinecone-local", "pinecone-hosted", "openai", "langsmith"]
    )
    asyncio.run(main(parser.parse_args().provider))
