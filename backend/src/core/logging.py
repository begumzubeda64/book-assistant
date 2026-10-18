"""Structured JSON logging.

Per security steering, logs must never contain secrets, tokens, credentials, or
raw private book text. Log safe identifiers only (request IDs, job IDs, status,
latency, error codes, operational metadata).
"""

from __future__ import annotations

import logging
from typing import Any

from pythonjsonlogger import json as json_logger


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging to emit structured JSON to stdout."""
    handler = logging.StreamHandler()
    formatter = json_logger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Align uvicorn's loggers with our JSON handler.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str, **context: Any) -> logging.LoggerAdapter[logging.Logger]:
    """Return a logger adapter that attaches safe contextual fields."""
    return logging.LoggerAdapter(logging.getLogger(name), context)
