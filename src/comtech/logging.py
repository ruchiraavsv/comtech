"""Bounded asynchronous JSON logging; one file writer per API process."""

import json
import logging
import queue
import sys
import threading
import time
from datetime import UTC, datetime
from logging.handlers import QueueHandler, RotatingFileHandler

from opentelemetry import trace

FIELDS = (
    "request_id",
    "thread_id",
    "run_id",
    "trace_id",
    "otel_trace_id",
    "otel_span_id",
    "error_type",
    "status",
)


class JsonFormatter(logging.Formatter):
    def __init__(self, environment="development"):
        super().__init__()
        self.environment = environment

    def format(self, record):
        data = {
            "schema_version": 1,
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "event": record.getMessage() if record.name.startswith("comtech") else "library_log",
            "logger": record.name,
            "service": "comtech-api",
            "environment": self.environment,
        }
        data.update({key: str(getattr(record, key)) for key in FIELDS if hasattr(record, key)})
        if record.exc_info and record.exc_info[0]:
            data["error_type"] = record.exc_info[0].__name__
        return json.dumps(data)


class Diagnostic:
    def __init__(self):
        self.last = 0.0

    def warn(self, event):
        now = time.monotonic()
        if now - self.last >= 5:
            self.last = now
            try:
                sys.stderr.write(json.dumps({"severity": "WARNING", "event": event}) + "\n")
            except OSError:
                pass


class SafeRotatingFileHandler(RotatingFileHandler):
    diagnostic = Diagnostic()

    def handleError(self, record):
        self.diagnostic.warn("log_file_write_failed")


class BoundedQueueHandler(QueueHandler):
    def __init__(self, records):
        super().__init__(records)
        self.diagnostic = Diagnostic()

    def prepare(self, record):
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            record.otel_trace_id = format(span.trace_id, "032x")
            record.otel_span_id = format(span.span_id, "016x")
        return super().prepare(record)

    def enqueue(self, record):
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.diagnostic.warn("log_queue_full_records_dropped")


class LoggingRuntime:
    def __init__(self, settings):
        self.records = queue.Queue(maxsize=2048)
        self.stopping = threading.Event()
        self.sinks = [logging.StreamHandler()]
        if settings.log_file_enabled:
            settings.log_directory.mkdir(parents=True, exist_ok=True)
            self.sinks.append(
                SafeRotatingFileHandler(
                    settings.log_directory / "api.jsonl",
                    maxBytes=settings.log_max_bytes,
                    backupCount=settings.log_backup_count,
                    encoding="utf-8",
                )
            )
        self.handler = BoundedQueueHandler(self.records)
        self.handler.setFormatter(JsonFormatter(settings.app_env))
        self.root = logging.getLogger()
        self.previous = self.root.handlers[:]
        self.previous_level = self.root.level
        self.root.handlers = [self.handler]
        self.root.setLevel(logging.INFO)
        self.server_loggers = []
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logger = logging.getLogger(name)
            self.server_loggers.append((logger, logger.handlers[:], logger.propagate))
            logger.handlers = []
            logger.propagate = True
        self.thread = threading.Thread(target=self._listen, daemon=True, name="log-writer")
        self.thread.start()

    def _listen(self):
        try:
            while not self.stopping.is_set() or not self.records.empty():
                try:
                    record = self.records.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    for sink in self.sinks:
                        sink.handle(record)
                finally:
                    self.records.task_done()
        finally:
            for sink in self.sinks:
                sink.close()

    def close(self):
        if self.handler in self.root.handlers:
            self.root.handlers = self.previous
            self.root.setLevel(self.previous_level)
            for logger, handlers, propagate in self.server_loggers:
                logger.handlers = handlers
                logger.propagate = propagate
        self.stopping.set()
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            self.handler.diagnostic.warn("log_shutdown_drain_timeout")


def configure_logging(settings=None):
    from comtech.settings import Settings

    return LoggingRuntime(settings or Settings())
