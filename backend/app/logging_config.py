"""One-line JSON logs containing only an allow-list of fields.

Anything not on the allow-list (message text, profile values, amounts) is dropped,
so passing it to ``extra=`` by mistake cannot leak it into the logs.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime

ALLOWED_FIELDS = frozenset(
    {
        "request_id",
        "session_ref",
        "method",
        "endpoint",
        "status_code",
        "duration_ms",
        "calculation_version",
        "ai_model_id",
        "ai_latency_ms",
        "error_code",
    }
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key in ALLOWED_FIELDS:
            if key in record.__dict__:
                payload[key] = record.__dict__[key]
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            # Stack frames only: an exception's message can quote the values being processed
            # (someone's income, say), so it never reaches the log.
            payload["traceback"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
