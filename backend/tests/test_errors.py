"""Tests for the consistent error envelope and error handlers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.errors import NotFoundError, register_exception_handlers
from src.core.middleware import RequestContextMiddleware


def test_unknown_route_returns_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"]


def test_app_error_maps_to_envelope() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("Book not found", code="BOOK_NOT_FOUND")

    with TestClient(app) as client:
        response = client.get("/boom")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "BOOK_NOT_FOUND"
    assert body["error"]["message"] == "Book not found"
    assert body["error"]["request_id"]


def test_unhandled_exception_does_not_leak_details() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret internal detail")

    # Do not let the TestClient re-raise so we can assert on the response.
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text
