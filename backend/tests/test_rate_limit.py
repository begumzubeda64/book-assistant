"""Tests for the per-user AI rate limiter and its enforcement on endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.core.config import Settings
from src.core.rate_limit import InMemoryRateLimiter
from src.main import create_app


def test_limiter_allows_up_to_limit_then_blocks() -> None:
    limiter = InMemoryRateLimiter(limit=3, window_seconds=60)
    assert all(limiter.check("u1", "op") for _ in range(3))
    assert limiter.check("u1", "op") is False  # 4th blocked


def test_limiter_is_per_user_and_per_operation() -> None:
    limiter = InMemoryRateLimiter(limit=1, window_seconds=60)
    assert limiter.check("u1", "read") is True
    assert limiter.check("u1", "read") is False
    # Different user and different operation are independent.
    assert limiter.check("u2", "read") is True
    assert limiter.check("u1", "discuss") is True


def test_limiter_window_expiry() -> None:
    limiter = InMemoryRateLimiter(limit=1, window_seconds=0.2)
    assert limiter.check("u1", "op") is True
    assert limiter.check("u1", "op") is False
    import time

    time.sleep(0.35)  # comfortably past the window to avoid timing flakiness
    assert limiter.check("u1", "op") is True  # window rolled over


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Very low limit so the endpoint trips quickly.
    settings = Settings(
        app_env="local",
        auth_allow_local_dev_user=True,
        ai_rate_limit_max=2,
        ai_rate_limit_window_seconds=60,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_reading_generate_is_rate_limited(client: TestClient) -> None:
    body = {"book_id": "b", "duration_minutes": 5, "mode": "balanced_read"}
    # The endpoint will 503 (no job storage) but the rate-limit dependency runs
    # first; after the limit it must be 429 regardless of downstream config.
    statuses = [
        client.post("/api/v1/reading/generate", json=body).status_code
        for _ in range(4)
    ]
    assert 429 in statuses
    # The 429s come after the allowed calls.
    assert statuses[-1] == 429
