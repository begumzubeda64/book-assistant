"""Tests for the RecommendationService and the recommendations API."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_recommendation_service
from src.core.config import Settings
from src.main import create_app
from src.models.recommendations import UserSignals
from src.schemas.books import BookMetadata
from src.services.recommendations import RecommendationService


def _book(book_id: str, **kw: object) -> BookMetadata:
    base: dict[str, object] = {
        "book_id": book_id,
        "provider": "google_books",
        "title": book_id,
        "authors": [],
        "categories": [],
    }
    base.update(kw)
    return BookMetadata.model_validate(base)


def _service(
    signals: UserSignals, candidates: list[BookMetadata]
) -> RecommendationService:
    async def signals_provider(_user_id: str) -> UserSignals:
        return signals

    async def candidate_provider(_signals: UserSignals) -> list[BookMetadata]:
        return candidates

    return RecommendationService(
        signals_provider=signals_provider,
        candidate_provider=candidate_provider,
    )


@pytest.mark.asyncio
async def test_recommend_sorts_by_score_and_drops_zero() -> None:
    signals = UserSignals(preferred_categories={"science"})
    candidates = [
        _book("weak", categories=["Fiction"]),  # no match -> dropped
        _book("strong", categories=["Science"]),  # match
    ]
    items = await _service(signals, candidates).recommend("u1")
    assert [i.book.book_id for i in items] == ["strong"]
    assert items[0].reason


@pytest.mark.asyncio
async def test_recommend_excludes_started_and_completed() -> None:
    signals = UserSignals(
        preferred_categories={"science"},
        started_book_ids={"started"},
        completed_book_ids={"done"},
    )
    candidates = [
        _book("started", categories=["Science"]),
        _book("done", categories=["Science"]),
        _book("fresh", categories=["Science"]),
    ]
    items = await _service(signals, candidates).recommend("u1")
    assert [i.book.book_id for i in items] == ["fresh"]


@pytest.mark.asyncio
async def test_recommend_respects_limit() -> None:
    signals = UserSignals(preferred_categories={"science"})
    candidates = [_book(f"b{i}", categories=["Science"]) for i in range(20)]
    items = await _service(signals, candidates).recommend("u1", limit=5)
    assert len(items) == 5


@pytest.mark.asyncio
async def test_recommend_empty_when_no_signals() -> None:
    items = await _service(UserSignals(), []).recommend("u1")
    assert items == []


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    app = create_app(settings)
    service = _service(
        UserSignals(preferred_categories={"science"}),
        [_book("rec1", categories=["Science"])],
    )
    app.dependency_overrides[get_recommendation_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client


def test_recommendations_api_returns_items(client: TestClient) -> None:
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["book"]["book_id"] == "rec1"
    assert body["items"][0]["reason"]
    assert body["items"][0]["score"] > 0


def test_recommendations_api_requires_auth() -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    app = create_app(settings)
    service = _service(UserSignals(), [])
    app.dependency_overrides[get_recommendation_service] = lambda: service
    with TestClient(app) as anon:
        response = anon.get("/api/v1/recommendations")
    assert response.status_code == 401
