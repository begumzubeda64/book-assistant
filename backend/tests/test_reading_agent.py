"""Tests for the adaptive-reading agent orchestration (fakes)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from src.agents.adaptive_reading.agent import AdaptiveReadingAgent
from src.agents.shared.types import PreparedChunk, SourceRef
from src.models.job import Job, JobStatus, JobType
from src.models.reading import ReadingFocus, ReadingMode


class FakeContent:
    def __init__(self, chunks: list[PreparedChunk]) -> None:
        self._chunks = chunks

    def get_chunks(
        self, *, user_id: str, book_id: str, chapter_id: str | None = None
    ) -> list[PreparedChunk]:
        return self._chunks


class FakeGenerator:
    def __init__(self, text: str = "A coherent condensed reading. " * 20) -> None:
        self.text = text
        self.calls = 0

    def generate(self, *, prompt: str, max_words: int) -> str:
        self.calls += 1
        return self.text


class FakeStore:
    def __init__(self) -> None:
        self.stored: dict[str, str] = {}

    def store_reading(self, *, user_id: str, reading_id: str, payload: str) -> str:
        self.stored[reading_id] = payload
        return f"s3://results/readings/{user_id}/{reading_id}.json"


class FakeJobRepo:
    def __init__(self, job: Job) -> None:
        self.job = job
        self.updates: list[dict[str, Any]] = []

    async def create(self, job: Job) -> Job:
        return job

    async def get(self, job_id: str) -> Job | None:
        return self.job if job_id == self.job.job_id else None

    async def find_by_idempotency_key(self, key: str) -> Job | None:
        return None

    async def update_status(self, job_id: str, status: JobStatus, **kw: Any) -> None:
        self.job.status = status
        self.updates.append({"status": status, **kw})


def _chunks() -> list[PreparedChunk]:
    return [
        PreparedChunk(
            chunk_id=f"b:p{i}:s0",
            text="Therefore the evidence shows the central claim. " * 10,
            word_count=80,
            source=SourceRef(book_id="b", page=i, chapter_title="Chapter 1"),
        )
        for i in range(1, 6)
    ]


def _job() -> Job:
    return Job(
        job_id="r1",
        user_id="u1",
        job_type=JobType.ADAPTIVE_READING,
        book_id="b",
        target_duration=5,
        mode=ReadingMode.BALANCED_READ.value,
        focus=ReadingFocus.KEY_ARGUMENTS.value,
    )


@pytest.mark.asyncio
async def test_reading_happy_path() -> None:
    store = FakeStore()
    gen = FakeGenerator()
    repo = FakeJobRepo(_job())
    agent = AdaptiveReadingAgent(
        content=FakeContent(_chunks()),
        generator=gen,
        store=store,
        jobs=repo,
    )

    await agent.handle_message({"job_id": "r1"})

    assert gen.calls == 1
    assert repo.updates[-1]["status"] is JobStatus.COMPLETED
    assert "s3://results" in repo.updates[-1]["result_location"]

    payload = json.loads(store.stored["r1"])
    assert payload["reading_id"] == "r1"
    assert payload["target_minutes"] == 5
    assert payload["target_words"] == 750
    assert payload["actual_words"] > 0
    assert payload["source_refs"]  # references retained


@pytest.mark.asyncio
async def test_reading_failure_marks_failed() -> None:
    class Boom:
        def generate(self, *, prompt: str, max_words: int) -> str:
            raise RuntimeError("model down")

    repo = FakeJobRepo(_job())
    agent = AdaptiveReadingAgent(
        content=FakeContent(_chunks()),
        generator=Boom(),
        store=FakeStore(),
        jobs=repo,
    )
    await agent.handle_message({"job_id": "r1"})
    assert repo.job.status is JobStatus.FAILED
    assert repo.updates[-1]["error_code"] == "READING_ERROR"


@pytest.mark.asyncio
async def test_reading_skips_terminal_job() -> None:
    job = _job()
    job.status = JobStatus.COMPLETED
    repo = FakeJobRepo(job)
    gen = FakeGenerator()
    agent = AdaptiveReadingAgent(
        content=FakeContent(_chunks()), generator=gen, store=FakeStore(), jobs=repo
    )
    await agent.handle_message({"job_id": "r1"})
    assert gen.calls == 0
    assert repo.updates == []
