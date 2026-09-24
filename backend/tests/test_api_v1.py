"""Tests for the API v1 router surface and auth dependency seam."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.dependencies import CurrentUser
from src.core.errors import register_exception_handlers
from src.core.middleware import RequestContextMiddleware


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/reading/generate"),
        ("get", "/api/v1/reading/r1"),
        ("post", "/api/v1/discussions"),
        ("get", "/api/v1/recommendations"),
    ],
)
def test_stub_routes_registered_and_not_implemented(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path)
    # Routes exist (not 404) and are declared placeholders (501).
    assert response.status_code == 501


def test_protected_route_without_token_fails_closed() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected(user: CurrentUser) -> dict[str, str]:  # noqa: ARG001
        return {"ok": "true"}

    with TestClient(app) as client:
        response = client.get("/protected")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_protected_route_with_token_not_yet_configured() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected(user: CurrentUser) -> dict[str, str]:  # noqa: ARG001
        return {"ok": "true"}

    with TestClient(app) as client:
        response = client.get(
            "/protected", headers={"Authorization": "Bearer sometoken"}
        )

    # Interface stub: a token is present but validation is not configured yet.
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
