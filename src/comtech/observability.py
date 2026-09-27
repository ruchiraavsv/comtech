"""Locally owned OTel provider; no global provider or cloud fallback."""

import asyncio
import json
import logging
import threading
from contextlib import contextmanager

from openinference.instrumentation import TraceConfig, using_session
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult
from opentelemetry.trace import Status, StatusCode

log = logging.getLogger("comtech.observability")


class LocalExporter(OTLPSpanExporter):
    def export(self, spans):
        try:
            result = super().export(spans)
        except Exception as error:
            log.warning("trace_export_failed", extra={"error_type": type(error).__name__})
            return SpanExportResult.FAILURE
        if result != SpanExportResult.SUCCESS:
            log.warning("trace_export_failed")
        return result


class Observability:
    def __init__(self, settings, processor=None):
        self.settings = settings
        self.provider = None
        self.instrumentor = None
        if settings.tracing_mode != "phoenix":
            return
        self.provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": "comtech-api",
                    "openinference.project.name": settings.phoenix_project_name,
                    "deployment.environment.name": settings.app_env,
                }
            ),
            shutdown_on_exit=False,
        )
        self.provider.add_span_processor(
            processor
            or BatchSpanProcessor(
                LocalExporter(endpoint=settings.phoenix_trace_endpoint, timeout=2, headers={}),
                max_queue_size=2048,
                max_export_batch_size=128,
                schedule_delay_millis=500,
                export_timeout_millis=3000,
            )
        )
        self.tracer = self.provider.get_tracer("comtech")
        self.instrumentor = LangChainInstrumentor()
        self.instrumentor.instrument(
            tracer_provider=self.provider,
            config=TraceConfig(
                hide_inputs=settings.trace_hide_inputs,
                hide_outputs=settings.trace_hide_outputs,
            ),
        )

    @contextmanager
    def execution(self, context, parent=None, inputs=None):
        if self.provider is None:
            yield None
            return
        attributes = {
            "openinference.span.kind": "CHAIN",
            "session.id": context["thread_id"],
            "metadata": json.dumps({**context, "parent_run_id": str(parent) if parent else None}),
            "input.mime_type": "text/plain",
            "input.value": "[REDACTED]"
            if self.settings.trace_hide_inputs
            else (str(inputs["messages"][-1].content) if inputs else "Resume from checkpoint"),
        }
        with (
            using_session(context["thread_id"]),
            self.tracer.start_as_current_span(
                "conversation_execution",
                attributes=attributes,
                record_exception=False,
                set_status_on_exception=False,
            ) as span,
        ):
            try:
                yield span
            except BaseException as error:
                self.outcome(
                    "interrupted" if isinstance(error, asyncio.CancelledError) else "failed"
                )
                raise

    def output(self, value):
        span = trace.get_current_span()
        span.set_attribute("output.mime_type", "text/plain")
        span.set_attribute(
            "output.value", "[REDACTED]" if self.settings.trace_hide_outputs else value
        )

    @staticmethod
    def outcome(status):
        span = trace.get_current_span()
        span.set_attribute("execution.status", status)
        span.set_status(Status(StatusCode.OK if status == "completed" else StatusCode.ERROR))

    def close(self, timeout=5):
        if self.instrumentor:
            self.instrumentor.uninstrument()
        if self.provider:
            # Some SDK versions do not enforce force_flush's timeout. Keep a
            # hard application-level bound without an executor shutdown waiting
            # indefinitely for a stuck exporter. This worker is diagnostic only.
            def drain():
                try:
                    self.provider.force_flush(timeout_millis=3000)
                finally:
                    self.provider.shutdown()

            worker = threading.Thread(target=drain, name="trace-shutdown", daemon=True)
            worker.start()
            worker.join(timeout=timeout)
            if worker.is_alive():
                log.warning("trace_shutdown_drain_timeout")
