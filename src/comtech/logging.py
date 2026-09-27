"""Structured, allowlisted operational logging (never request bodies or credentials)."""

import json
import logging
from datetime import UTC, datetime

FIELDS = ("request_id", "thread_id", "run_id", "trace_id", "error_type", "status")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        data.update({key: getattr(record, key) for key in FIELDS if hasattr(record, key)})
        if record.exc_info and record.exc_info[0]:
            data["error_type"] = record.exc_info[0].__name__
        return json.dumps(data)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Avoid HTTP URLs/headers from verbose SDK logging.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
