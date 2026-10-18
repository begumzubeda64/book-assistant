"""API tests for the progress router (self-scoped, auth required)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_progress_service
from src.core.config import Settings
from src.main import create_app
from src.models.progress import Progress
from src.schemas.progress import ProgressUpdate

DEV_USER = "local-dev-user"


class FakeProgressService:
    """Tracks progress keyed by (user_id, book_id)."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], Progress] = {
            ("someone-else", "book1"): Progress(
                user_id="someone-else", book_id="book1", position=999
            )
        }

    async def get_progress(self, user_id: str, book_id: str) -> Progress | None:
        return self.store.get((user_id, book_id))

    async def save_progress(
        self, user_id: str, book_id: str, update: ProgressUpdate
    ) -> Progress:
        progress = Progress(
            user_id=user_id,
            book_id=book_id,
            chapter_id=update.chapter_id,
            position=update.position,
            selected_duration=update.selected_duration,
            selected_mode=update.selected_mode,
            completed=update.completed,
        )
        self.store[(user_id, book_id)] = progress
        return progress


@pytest.fixture
def service() -> FakeProgressService:
    return FakeProgressService()


@pytest.fixture
def client(service: FakeProgressService) -> Iterator[TestClient]:
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    app = create_app(settings)
    app.dependency_overrides[get_progress_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client


def test_put_then_get_roundtrip(client: TestClient) -> None:
    put = client.put(
        "/api/v1/progress/book42",
        json={"position": 500, "selected_mode": "quick_read", "chapter_id": "c1"},
    )
    assert put.status_code == 200
    assert put.json()["position"] == 500

    got = client.get("/api/v1/progress/book42")
    assert got.status_code == 200
    body = got.json()
    assert body["book_id"] == "book42"
    assert body["selected_mode"] == "quick_read"


def test_get_missing_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/progress/never-read")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROGRESS_NOT_FOUND"


def test_user_cannot_see_another_users_progress(client: TestClient) -> None:
    # 'someone-else' has progress for book1; the authenticated dev user does not.
    response = client.get("/api/v1/progress/book1")
    assert response.status_code == 404


def test_put_rejects_negative_position(client: TestClient) -> None:
    response = client.put("/api/v1/progress/book42", json={"position": -1})
    assert response.status_code == 422


def test_progress_requires_auth(service: FakeProgressService) -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    app = create_app(settings)
    app.dependency_overrides[get_progress_service] = lambda: service
    with TestClient(app) as anon:
        response = anon.get("/api/v1/progress/book42")
    assert response.status_code == 401
