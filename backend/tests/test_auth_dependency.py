"""Tests for the get_current_user dependency (bypass + fail-closed behavior)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.dependencies import CurrentUser
from src.core.config import Settings
from src.core.errors import register_exception_handlers
from src.core.middleware import RequestContextMiddleware


def _app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    # Override the settings dependency used inside get_current_user.
    from src.core.config import get_settings

    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/whoami")
    async def whoami(user: CurrentUser) -> dict[str, str]:
        return {"user_id": user.user_id}

    return app


def test_local_dev_bypass_returns_dev_user() -> None:
    settings = Settings(
        app_env="local",
        auth_allow_local_dev_user=True,
        local_dev_user_id="dev-abc",
    )
    with TestClient(_app(settings)) as client:
        response = client.get("/whoami")
    assert response.status_code == 200
    assert response.json()["user_id"] == "dev-abc"


def test_bypass_ignored_when_not_local() -> None:
    # Bypass flag on, but environment is not local -> must fail closed.
    settings = Settings(app_env="dev", auth_allow_local_dev_user=True)
    with TestClient(_app(settings)) as client:
        response = client.get("/whoami")
    assert response.status_code == 401


def test_no_token_fails_closed() -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    with TestClient(_app(settings)) as client:
        response = client.get("/whoami")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_token_present_but_cognito_unconfigured_fails_closed() -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    with TestClient(_app(settings)) as client:
        response = client.get("/whoami", headers={"Authorization": "Bearer x"})
    assert response.status_code == 401
