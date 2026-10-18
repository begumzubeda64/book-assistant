"""API tests for the adaptive-reading router."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import (
    get_job_service,
    get_reading_result_repository,
)
from src.core.config import Settings
from src.main import create_app
from src.models.job import Job, JobStatus, JobType


class FakeJobService:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create_and_enqueue(self, **kwargs: Any) -> Job:
        self.created.append(kwargs)
        return Job(
            job_id="r1",
            user_id=kwargs["user_id"],
            job_type=JobType.ADAPTIVE_READING,
            book_id=kwargs.get("book_id"),
            status=JobStatus.QUEUED,
        )


class FakeReadingRepo:
    def __init__(self) -> None:
        self.results = {
            ("local-dev-user", "r1"): {
                "reading_id": "r1",
                "book_id": "b",
                "mode": "balanced_read",
                "focus": "key_ideas",
                "target_minutes": 5,
                "target_words": 750,
                "actual_words": 700,
                "content": "prose",
                "source_refs": [],
                "created_at": datetime.now(UTC).isoformat(),
            }
        }

    async def get(self, user_id: str, reading_id: str):
        return self.results.get((user_id, reading_id))


@pytest.fixture
def job_service() -> FakeJobService:
    return FakeJobService()


@pytest.fixture
def client(job_service: FakeJobService) -> Iterator[TestClient]:
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    app = create_app(settings)
    app.dependency_overrides[get_job_service] = lambda: job_service
    app.dependency_overrides[get_reading_result_repository] = FakeReadingRepo
    with TestClient(app) as test_client:
        yield test_client


def test_generate_creates_job(client: TestClient, job_service: FakeJobService) -> None:
    response = client.post(
        "/api/v1/reading/generate",
        json={
            "book_id": "b",
            "duration_minutes": 5,
            "mode": "balanced_read",
            "focus": "key_ideas",
        },
    )
    assert response.status_code == 202
    assert response.json()["job_id"] == "r1"
    assert job_service.created[0]["job_type"].value == "ADAPTIVE_READING"
    assert job_service.created[0]["target_duration"] == 5


def test_generate_rejects_unsupported_duration(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reading/generate",
        json={"book_id": "b", "duration_minutes": 7, "mode": "quick_read"},
    )
    assert response.status_code == 422


def test_generate_rejects_bad_mode(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reading/generate",
        json={"book_id": "b", "duration_minutes": 5, "mode": "turbo"},
    )
    assert response.status_code == 422


def test_get_reading_found(client: TestClient) -> None:
    response = client.get("/api/v1/reading/r1")
    assert response.status_code == 200
    assert response.json()["reading_id"] == "r1"


def test_get_reading_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/reading/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "READING_NOT_FOUND"


def test_reading_requires_auth(job_service: FakeJobService) -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    app = create_app(settings)
    app.dependency_overrides[get_job_service] = lambda: job_service
    with TestClient(app) as anon:
        response = anon.post(
            "/api/v1/reading/generate",
            json={"book_id": "b", "duration_minutes": 5, "mode": "quick_read"},
        )
    assert response.status_code == 401
