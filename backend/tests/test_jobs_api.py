"""API tests for the jobs router (ownership enforcement)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_job_service
from src.core.config import Settings
from src.core.security.authorization import assert_owner
from src.core.security.cognito import AuthenticatedUser
from src.main import create_app
from src.models.job import Job, JobType


class FakeJobService:
    def __init__(self) -> None:
        self.jobs = {
            "mine": Job(
                job_id="mine",
                user_id="local-dev-user",
                job_type=JobType.BOOK_INGESTION,
            ),
            "theirs": Job(
                job_id="theirs",
                user_id="someone-else",
                job_type=JobType.BOOK_INGESTION,
            ),
        }

    async def get_for_user(self, job_id: str, user: AuthenticatedUser) -> Job:
        job = self.jobs.get(job_id)
        assert_owner(user, job.user_id if job else None, resource="job")
        assert job is not None
        return job


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    app = create_app(settings)
    app.dependency_overrides[get_job_service] = lambda: FakeJobService()
    with TestClient(app) as test_client:
        yield test_client


def test_get_own_job(client: TestClient) -> None:
    response = client.get("/api/v1/jobs/mine")
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "mine"
    assert body["status"] == "QUEUED"


def test_get_other_users_job_is_forbidden(client: TestClient) -> None:
    response = client.get("/api/v1/jobs/theirs")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_get_missing_job_is_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/jobs/unknown")
    assert response.status_code == 404


def test_jobs_require_auth() -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    app = create_app(settings)
    app.dependency_overrides[get_job_service] = lambda: FakeJobService()
    with TestClient(app) as anon:
        response = anon.get("/api/v1/jobs/mine")
    assert response.status_code == 401
