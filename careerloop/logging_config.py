"""
CareerLoop structured logging configuration.

Usage — call once at process start, before any pipeline code runs::

    from careerloop.logging_config import configure
    configure()

All loggers across the process then emit JSON lines to ``logs/careerloop.jsonl``.
Console logging is opt-in via ``DEBUG_CONSOLE_LOGS=true``.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

# ── JSON formatter ──────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            doc.update(extra)
        return json.dumps(doc, ensure_ascii=False)


# ── Public API ──────────────────────────────────────────────────────────

_configured: bool = False


def configure(log_dir: str = "logs") -> None:
    """Idempotent structured-JSON logging setup.

    * File handler: ``{log_dir}/careerloop.jsonl`` (INFO+).
    * Stream handler: ``stderr`` only when ``DEBUG_CONSOLE_LOGS=true``.

    Safe to call from multiple entry-points — only applies once.
    """
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    # Clear any legacy basicConfig handlers so we own the format.
    if root.handlers:
        root.handlers.clear()

    file_handler = logging.FileHandler(
        os.path.join(log_dir, "careerloop.jsonl"), encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(_JsonFormatter())

    root.setLevel(logging.INFO)
    root.addHandler(file_handler)

    if os.getenv("DEBUG_CONSOLE_LOGS", "").strip().lower() == "true":
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(_JsonFormatter())
        root.addHandler(stream_handler)
