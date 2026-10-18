"""Job domain model.

An asynchronous unit of work created by the API and executed off the request
path by a LangGraph agent on AgentCore Runtime. The job record in DynamoDB plus
the SQS message form the durable async boundary (design.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class JobType(StrEnum):
    BOOK_INGESTION = "BOOK_INGESTION"
    ADAPTIVE_READING = "ADAPTIVE_READING"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def _now() -> datetime:
    return datetime.now(UTC)


class Job(BaseModel):
    """A tracked asynchronous job."""

    job_id: str
    user_id: str
    job_type: JobType
    status: JobStatus = JobStatus.QUEUED

    book_id: str | None = None
    chapter_id: str | None = None

    # Adaptive-reading parameters (unused for ingestion).
    target_duration: int | None = None
    mode: str | None = None
    focus: str | None = None

    # Idempotency: a deterministic key so retries do not create duplicate jobs.
    idempotency_key: str | None = None

    progress: int = 0
    result_location: str | None = None
    error_code: str | None = None

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
