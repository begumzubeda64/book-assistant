"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.core.config import Settings
from src.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Deterministic settings for tests."""
    return Settings(app_env="local", log_level="WARNING")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A TestClient bound to a freshly built app."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
