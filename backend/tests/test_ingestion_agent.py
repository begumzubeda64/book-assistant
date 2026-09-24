"""Tests for the ingestion graph + agent orchestration (with fakes)."""

from __future__ import annotations

import io
from typing import Any

import pytest
from src.agents.ingestion.agent import IngestionAgent
from src.agents.shared.types import PreparedChunk
from src.models.job import Job, JobStatus, JobType


def _make_pdf(pages_text: list[str]) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in pages_text:
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class FakeContent:
    def __init__(self, pdf: bytes) -> None:
        self._pdf = pdf
        self.calls: list[tuple[str, str]] = []

    def fetch_pdf_bytes(self, user_id: str, object_key: str) -> bytes:
        self.calls.append((user_id, object_key))
        return self._pdf


class FailingContent:
    def fetch_pdf_bytes(self, user_id: str, object_key: str) -> bytes:
        raise RuntimeError("s3 down")


class FakeKB:
    def __init__(self) -> None:
        self.ingested: list[tuple[str, str, int]] = []

    def ingest_chunks(
        self, *, user_id: str, book_id: str, chunks: list[PreparedChunk]
    ) -> str:
        self.ingested.append((user_id, book_id, len(chunks)))
        return "ingestion-ref-1"


class FakeJobRepo:
    def __init__(self, job: Job) -> None:
        self.job = job
        self.status_updates: list[dict[str, Any]] = []

    async def create(self, job: Job) -> Job:
        return job

    async def get(self, job_id: str) -> Job | None:
        return self.job if job_id == self.job.job_id else None

    async def find_by_idempotency_key(self, key: str) -> Job | None:
        return None

    async def update_status(self, job_id: str, status: JobStatus, **kw: Any) -> None:
        self.job.status = status
        self.status_updates.append({"status": status, **kw})


def _job(status: JobStatus = JobStatus.QUEUED) -> Job:
    return Job(
        job_id="j1",
        user_id="u1",
        job_type=JobType.BOOK_INGESTION,
        book_id="book1",
        status=status,
    )


@pytest.mark.asyncio
async def test_ingestion_happy_path() -> None:
    pdf = _make_pdf(["a", "b"])
    content = FakeContent(pdf)
    kb = FakeKB()
    repo = FakeJobRepo(_job())
    agent = IngestionAgent(content=content, knowledge_base=kb, jobs=repo)

    await agent.handle_message(
        {"job_id": "j1", "object_key": "uploads/u1/book1.pdf"}
    )

    statuses = [u["status"] for u in repo.status_updates]
    assert JobStatus.PROCESSING in statuses
    assert statuses[-1] is JobStatus.COMPLETED
    assert repo.status_updates[-1]["result_location"] == "ingestion-ref-1"
    assert content.calls == [("u1", "uploads/u1/book1.pdf")]


@pytest.mark.asyncio
async def test_ingestion_failure_marks_job_failed() -> None:
    repo = FakeJobRepo(_job())
    agent = IngestionAgent(
        content=FailingContent(), knowledge_base=FakeKB(), jobs=repo
    )

    await agent.handle_message({"job_id": "j1"})

    assert repo.job.status is JobStatus.FAILED
    assert repo.status_updates[-1]["error_code"] == "INGESTION_ERROR"


@pytest.mark.asyncio
async def test_ingestion_skips_terminal_job() -> None:
    repo = FakeJobRepo(_job(status=JobStatus.COMPLETED))
    kb = FakeKB()
    agent = IngestionAgent(
        content=FakeContent(_make_pdf(["a"])), knowledge_base=kb, jobs=repo
    )

    await agent.handle_message({"job_id": "j1"})

    assert repo.status_updates == []  # nothing re-run
    assert kb.ingested == []


@pytest.mark.asyncio
async def test_ingestion_missing_job_is_noop() -> None:
    repo = FakeJobRepo(_job())
    agent = IngestionAgent(
        content=FakeContent(_make_pdf(["a"])), knowledge_base=FakeKB(), jobs=repo
    )
    await agent.handle_message({"job_id": "does-not-exist"})
    assert repo.status_updates == []
