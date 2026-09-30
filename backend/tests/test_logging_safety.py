"""Guards for safe structured logging (security.md: never log secrets).

These tests assert the two places most likely to leak — the request-context
middleware and the centralized error handlers — emit only safe metadata (never
tokens, credentials, or exception messages).
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.errors import register_exception_handlers
from src.core.logging import configure_logging
from src.core.middleware import RequestContextMiddleware

# Values that must never appear in logs.
SECRET_TOKEN = "supersecrettokenvalue12345"
SECRET_DETAIL = "secret-internal-detail-xyz"


def _capture_logs(caplog_handler: list[str]) -> logging.Handler:
    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            caplog_handler.append(self.format(record))

    handler = _ListHandler()
    handler.setFormatter(logging.Formatter("%(message)s %(name)s"))
    return handler


def test_request_logging_excludes_authorization_header() -> None:
    configure_logging("INFO")
    records: list[str] = []
    handler = _capture_logs(records)
    logging.getLogger("src.core.middleware").addHandler(handler)

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    try:
        with TestClient(app) as client:
            client.get(
                "/ping", headers={"Authorization": f"Bearer {SECRET_TOKEN}"}
            )
    finally:
        logging.getLogger("src.core.middleware").removeHandler(handler)

    joined = "\n".join(records)
    assert "request_completed" in joined
    assert SECRET_TOKEN not in joined  # token never logged


def test_unhandled_error_does_not_log_exception_message() -> None:
    configure_logging("INFO")
    records: list[str] = []
    handler = _capture_logs(records)
    logging.getLogger("src.core.errors").addHandler(handler)

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError(SECRET_DETAIL)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/boom")
    finally:
        logging.getLogger("src.core.errors").removeHandler(handler)

    assert response.status_code == 500
    joined = "\n".join(records)
    # Only the exception type is logged, never its (potentially sensitive) message.
    assert "unhandled_error" in joined
    assert SECRET_DETAIL not in joined
    assert SECRET_DETAIL not in response.text


def test_json_formatter_emits_structured_fields() -> None:
    configure_logging("INFO")
    root = logging.getLogger()
    formatter = root.handlers[0].formatter
    assert formatter is not None
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "event_name", None, None
    )
    record.job_id = "job-1"  # type: ignore[attr-defined]
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["message"] == "event_name"
    assert parsed["job_id"] == "job-1"
    assert parsed["level"] == "INFO"
