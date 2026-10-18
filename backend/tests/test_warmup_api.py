"""Tests for POST /api/v1/warmup (auth + no-op when unconfigured)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.core.config import Settings
from src.main import create_app


@pytest.fixture
def client():
    # Local dev: no agent runtime ARNs configured -> nothing to warm, 202.
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    with TestClient(create_app(settings)) as c:
        yield c


def test_warmup_returns_202_and_schedules_zero_when_unconfigured(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/warmup")
    assert response.status_code == 202
    assert response.json() == {"scheduled": 0}


def test_warmup_requires_auth() -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    with TestClient(create_app(settings)) as anon:
        response = anon.post("/api/v1/warmup")
    assert response.status_code == 401
