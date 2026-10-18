"""Tests for the API v1 router surface and auth dependency seam."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.dependencies import CurrentUser
from src.core.errors import register_exception_handlers
from src.core.middleware import RequestContextMiddleware

# All API v1 routes are now implemented (no 501 stubs remain). The tests below
# cover the shared auth-dependency behavior applied across those routes.


def _fail_closed_app() -> FastAPI:
    """A bare app whose settings have no bypass and no Cognito configured.

    Overriding get_settings makes the test hermetic regardless of ambient
    environment variables (e.g. a local-dev shell with the bypass enabled).
    """
    from src.core.config import Settings, get_settings

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="local", auth_allow_local_dev_user=False
    )

    @app.get("/protected")
    async def protected(user: CurrentUser) -> dict[str, str]:  # noqa: ARG001
        return {"ok": "true"}

    return app


def test_protected_route_without_token_fails_closed() -> None:
    with TestClient(_fail_closed_app()) as client:
        response = client.get("/protected")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_protected_route_with_token_not_yet_configured() -> None:
    with TestClient(_fail_closed_app()) as client:
        response = client.get(
            "/protected", headers={"Authorization": "Bearer sometoken"}
        )

    # Interface stub: a token is present but validation is not configured yet.
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
