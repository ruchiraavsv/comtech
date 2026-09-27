import asyncio
import json
import logging
import queue
import threading
import time
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import tracing_context
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from comtech.graph import build_graph
from comtech.logging import BoundedQueueHandler, SafeRotatingFileHandler, configure_logging
from comtech.observability import Observability
from comtech.settings import Settings


def test_modes_require_only_hosted_credentials():
    assert Settings(_env_file=None, observability_mode="phoenix").tracing_mode == "phoenix"
    with pytest.raises(ValueError, match="conflicts"):
        Settings(_env_file=None, observability_mode="phoenix", langsmith_tracing=True)
    with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
        Settings(_env_file=None, observability_mode="langsmith")


def test_log_rotation_append_and_allowlisting(tmp_path):
    cfg = Settings(
        _env_file=None,
        log_file_enabled=True,
        log_directory=tmp_path,
        log_max_bytes=1200,
        log_backup_count=2,
    )
    for phase in range(2):
        runtime = configure_logging(cfg)
        try:
            for index in range(10):
                logging.getLogger("comtech.test").info(
                    f"event_{phase}_{index}", extra={"run_id": "run-1", "api_key": "SECRET"}
                )
        finally:
            runtime.close()
    files = list(tmp_path.glob("api.jsonl*"))
    assert len(files) == 3
    content = "".join(p.read_text() for p in files)
    records = [json.loads(line) for line in content.splitlines()]
    assert "SECRET" not in content
    assert any(r["event"] == "event_1_9" for r in records)
    before = (tmp_path / "api.jsonl").read_text()
    runtime = configure_logging(cfg)
    runtime.close()
    assert (tmp_path / "api.jsonl").read_text() == before


def test_full_queue_drops_without_blocking(capsys):
    handler = BoundedQueueHandler(queue.Queue(maxsize=1))
    record = logging.LogRecord("comtech", logging.INFO, "", 0, "event", (), None)
    handler.enqueue(record)
    handler.enqueue(record)
    assert "log_queue_full_records_dropped" in capsys.readouterr().err


def test_runtime_file_failure_is_reported_without_raising(tmp_path, monkeypatch, capsys):
    handler = SafeRotatingFileHandler(tmp_path / "failure.jsonl")

    def fail(record):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(handler, "shouldRollover", fail)
    try:
        handler.emit(logging.LogRecord("comtech", logging.ERROR, "", 0, "event", (), None))
        assert "log_file_write_failed" in capsys.readouterr().err
    finally:
        handler.close()


def test_shutdown_is_bounded_even_if_sdk_flush_stalls():
    observation = Observability(Settings(_env_file=None, observability_mode="off"))
    release = threading.Event()
    stopped = threading.Event()

    class SlowProvider:
        def force_flush(self, timeout_millis):
            release.wait(2)

        def shutdown(self):
            stopped.set()

    observation.provider = SlowProvider()
    start = time.monotonic()
    try:
        observation.close(timeout=0.02)
        assert time.monotonic() - start < 0.5
    finally:
        release.set()
        assert stopped.wait(2)


async def test_cancellation_and_input_output_masking():
    cfg = Settings(
        _env_file=None,
        observability_mode="phoenix",
        trace_hide_inputs=True,
        trace_hide_outputs=True,
    )
    exporter = InMemorySpanExporter()
    observation = Observability(cfg, SimpleSpanProcessor(exporter))
    context = {"run_id": str(uuid4()), "thread_id": str(uuid4())}
    try:
        with (
            pytest.raises(asyncio.CancelledError),
            observation.execution(
                context, inputs={"messages": [HumanMessage(content="PRIVATE_INPUT")]}
            ),
            tracing_context(enabled=False),
        ):
            graph = build_graph(InMemorySaver(), 0)
            await graph.ainvoke(
                {"messages": [HumanMessage(content="PRIVATE_INPUT")]},
                {"configurable": {"thread_id": context["thread_id"]}},
            )
            observation.output("PRIVATE_OUTPUT")
            raise asyncio.CancelledError
        spans = exporter.get_finished_spans()
        root = next(s for s in spans if s.name == "conversation_execution")
        assert root.attributes["execution.status"] == "interrupted"
        assert root.status.status_code.name == "ERROR"
        serialized = "".join(str(s.attributes) for s in spans)
        assert "PRIVATE_INPUT" not in serialized
        assert "PRIVATE_OUTPUT" not in serialized
        assert root.resource.attributes["openinference.project.name"] == "comtech-local"
    finally:
        observation.close()


async def test_graph_trace_hierarchy_concurrency_failures_and_reload(tmp_path):
    cfg = Settings(
        _env_file=None, observability_mode="phoenix", log_file_enabled=True, log_directory=tmp_path
    )
    logs = configure_logging(cfg)
    try:
        # Repeat initialization in the same process to catch stale instrumentation.
        for _ in range(2):
            exporter = InMemorySpanExporter()
            observation = Observability(cfg, SimpleSpanProcessor(exporter))
            graph = build_graph(InMemorySaver(), 0.01)

            async def execute(message, observation=observation, graph=graph):
                context = {"run_id": str(uuid4()), "thread_id": str(uuid4())}
                with observation.execution(context), tracing_context(enabled=False):
                    logging.getLogger("comtech.test").info("execution", extra=context)
                    try:
                        await graph.ainvoke(
                            {"messages": [HumanMessage(content=message)]},
                            {"configurable": {"thread_id": context["thread_id"]}},
                        )
                    except ValueError:
                        observation.outcome("failed")
                    else:
                        observation.outcome("completed")

            try:
                await asyncio.gather(execute("hello"), execute("/fail"))
                spans = exporter.get_finished_spans()
                roots = [s for s in spans if s.name == "conversation_execution"]
                assert len(roots) == 2
                assert len({s.context.trace_id for s in roots}) == 2
                assert {s.attributes["execution.status"] for s in roots} == {"completed", "failed"}
                for root in roots:
                    children = [
                        s
                        for s in spans
                        if s.context.trace_id == root.context.trace_id and s.name == "mock_node"
                    ]
                    assert len(children) == 1
                    assert "input.value" in children[0].attributes
                    assert children[0].parent is not None
            finally:
                observation.close()
    finally:
        logs.close()
    records = [json.loads(line) for line in (tmp_path / "api.jsonl").read_text().splitlines()]
    executions = [r for r in records if r["event"] == "execution"]
    assert len(executions) == 4
    assert all(len(r["otel_trace_id"]) == 32 for r in executions)
