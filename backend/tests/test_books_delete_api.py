"""API tests for DELETE /api/v1/books/{book_id} (auth + delegation)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_book_deletion_service
from src.core.config import Settings
from src.main import create_app


class FakeDeletionService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def delete_book(self, *, user_id: str, book_id: str) -> dict[str, Any]:
        self.calls.append((user_id, book_id))
        return {
            "deleted_pdf": True,
            "deleted_chunks": 2,
            "deleted_readings": 1,
            "deleted_conversations": 0,
            "deleted_progress": True,
        }


@pytest.fixture
def service() -> FakeDeletionService:
    return FakeDeletionService()


@pytest.fixture
def client(service: FakeDeletionService):
    # Local dev auth bypass resolves a synthetic user, so the route is reachable.
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    app = create_app(settings)
    app.dependency_overrides[get_book_deletion_service] = lambda: service
    with TestClient(app) as c:
        yield c


def test_delete_book_returns_204_and_delegates(
    client: TestClient, service: FakeDeletionService
) -> None:
    response = client.delete("/api/v1/books/book-123")
    assert response.status_code == 204
    # Delegated with the authenticated user's id (the local-dev user) + book id.
    assert len(service.calls) == 1
    assert service.calls[0][1] == "book-123"


def test_delete_book_requires_auth(service: FakeDeletionService) -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    app = create_app(settings)
    app.dependency_overrides[get_book_deletion_service] = lambda: service
    with TestClient(app) as anon:
        response = anon.delete("/api/v1/books/book-123")
    assert response.status_code == 401
    assert service.calls == []
