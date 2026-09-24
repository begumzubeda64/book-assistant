"""Tests for the upload + job services (presign validation, ingest idempotency)."""

from __future__ import annotations

from typing import Any

import pytest
from src.core.errors import ForbiddenError, ValidationAppError
from src.core.security.cognito import AuthenticatedUser
from src.models.job import Job, JobType
from src.schemas.uploads import PresignUploadRequest
from src.services.jobs import JobService
from src.services.uploads import MAX_UPLOAD_BYTES, UploadService

USER = AuthenticatedUser(user_id="u1")


class FakeStorage:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists
        self.presigned: list[str] = []

    def presign_put(
        self, object_key: str, *, content_type: str, expires_in: int
    ) -> str:
        self.presigned.append(object_key)
        return f"https://s3.local/{object_key}?sig=abc"

    def object_exists(self, object_key: str) -> bool:
        return self.exists


class FakeJobRepo:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.by_key: dict[str, Job] = {}

    async def create(self, job: Job) -> Job:
        if job.idempotency_key and job.idempotency_key in self.by_key:
            return self.by_key[job.idempotency_key]
        self.jobs[job.job_id] = job
        if job.idempotency_key:
            self.by_key[job.idempotency_key] = job
        return job

    async def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    async def find_by_idempotency_key(self, key: str) -> Job | None:
        return self.by_key.get(key)

    async def update_status(self, *a: Any, **k: Any) -> None:
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_job(self, message: dict[str, Any], *, dedup_id: str | None = None) -> None:
        self.sent.append(message)


def _upload_service(
    storage: FakeStorage, queue: FakeQueue, *, verify: bool = False
) -> tuple[UploadService, FakeQueue]:
    jobs = JobService(repository=FakeJobRepo(), queue=queue)
    return (
        UploadService(storage=storage, jobs=jobs, verify_object_exists=verify),
        queue,
    )


def _presign_req(**kw: Any) -> PresignUploadRequest:
    base: dict[str, Any] = {
        "filename": "book.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1000,
        "authorized_confirmation": True,
    }
    base.update(kw)
    return PresignUploadRequest(**base)


def test_presign_success() -> None:
    storage = FakeStorage()
    service, _ = _upload_service(storage, FakeQueue())
    resp = service.presign(USER, _presign_req())
    assert resp.object_key.startswith("uploads/u1/")
    assert resp.object_key.endswith(".pdf")
    assert resp.upload_url
    assert resp.required_headers["Content-Type"] == "application/pdf"


def test_presign_rejects_non_pdf() -> None:
    service, _ = _upload_service(FakeStorage(), FakeQueue())
    with pytest.raises(ValidationAppError):
        service.presign(USER, _presign_req(content_type="image/png"))


def test_presign_rejects_oversize() -> None:
    service, _ = _upload_service(FakeStorage(), FakeQueue())
    with pytest.raises(ValidationAppError):
        service.presign(USER, _presign_req(size_bytes=MAX_UPLOAD_BYTES + 1))


def test_presign_requires_authorization_confirmation() -> None:
    # Schema-level enforcement: confirmation must be True.
    with pytest.raises(ValueError):
        _presign_req(authorized_confirmation=False)


@pytest.mark.asyncio
async def test_complete_creates_ingestion_job_and_enqueues() -> None:
    storage = FakeStorage()
    service, queue = _upload_service(storage, FakeQueue())
    resp = service.presign(USER, _presign_req())

    job = await service.complete_and_ingest(USER, resp.book_id, resp.object_key)

    assert job.job_type is JobType.BOOK_INGESTION
    assert job.book_id == resp.book_id
    assert len(queue.sent) == 1
    assert queue.sent[0]["job_type"] == "BOOK_INGESTION"


@pytest.mark.asyncio
async def test_complete_is_idempotent() -> None:
    storage = FakeStorage()
    service, queue = _upload_service(storage, FakeQueue())
    resp = service.presign(USER, _presign_req())

    j1 = await service.complete_and_ingest(USER, resp.book_id, resp.object_key)
    j2 = await service.complete_and_ingest(USER, resp.book_id, resp.object_key)

    assert j1.job_id == j2.job_id
    assert len(queue.sent) == 1  # only enqueued once


@pytest.mark.asyncio
async def test_complete_rejects_foreign_key() -> None:
    service, _ = _upload_service(FakeStorage(), FakeQueue())
    with pytest.raises(ForbiddenError):
        await service.complete_and_ingest(
            USER, "book1", "uploads/other-user/book1.pdf"
        )


@pytest.mark.asyncio
async def test_complete_rejects_key_book_mismatch() -> None:
    service, _ = _upload_service(FakeStorage(), FakeQueue())
    with pytest.raises(ValidationAppError):
        await service.complete_and_ingest(
            USER, "book1", "uploads/u1/different-book.pdf"
        )


@pytest.mark.asyncio
async def test_complete_verifies_object_exists_when_enabled() -> None:
    storage = FakeStorage(exists=False)
    service, _ = _upload_service(storage, FakeQueue(), verify=True)
    resp = service.presign(USER, _presign_req())
    with pytest.raises(ValidationAppError):
        await service.complete_and_ingest(USER, resp.book_id, resp.object_key)
