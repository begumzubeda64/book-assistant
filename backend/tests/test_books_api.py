"""API tests for the book discovery router."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_book_discovery_service
from src.core.config import Settings
from src.main import create_app
from src.schemas.books import BookMetadata


class FakeService:
    def __init__(self) -> None:
        self.books = {
            "google_books:1": BookMetadata(
                book_id="google_books:1", provider="google_books", title="Dune"
            )
        }

    async def search(self, query: str, *, limit: int = 20):
        return list(self.books.values())

    async def get_book(self, book_id: str):
        return self.books.get(book_id)


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Local dev bypass supplies an authenticated user without a real token.
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    app = create_app(settings)

    async def _fake_service() -> FakeService:
        return FakeService()

    app.dependency_overrides[get_book_discovery_service] = _fake_service
    with TestClient(app) as test_client:
        yield test_client


def test_search_returns_results(client: TestClient) -> None:
    response = client.get("/api/v1/books/search", params={"q": "dune"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "dune"
    assert body["items"][0]["book_id"] == "google_books:1"


def test_search_requires_query(client: TestClient) -> None:
    response = client.get("/api/v1/books/search")
    assert response.status_code == 422


def test_search_rejects_empty_query(client: TestClient) -> None:
    response = client.get("/api/v1/books/search", params={"q": ""})
    assert response.status_code == 422


def test_get_book_found(client: TestClient) -> None:
    response = client.get("/api/v1/books/google_books:1")
    assert response.status_code == 200
    assert response.json()["title"] == "Dune"


def test_get_book_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/books/google_books:missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BOOK_NOT_FOUND"


def test_search_requires_auth() -> None:
    # No bypass, no token -> fail closed.
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    app = create_app(settings)
    with TestClient(app) as anon:
        response = anon.get("/api/v1/books/search", params={"q": "dune"})
    assert response.status_code == 401
