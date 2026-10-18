"""Job API schemas."""

from __future__ import annotations

from datetime import datetime

from src.models.job import JobStatus, JobType
from src.schemas.base import APIModel


class JobResponse(APIModel):
    """Public view of an async job's status."""

    job_id: str
    job_type: JobType
    status: JobStatus
    book_id: str | None = None
    progress: int = 0
    result_location: str | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class JobCreatedResponse(APIModel):
    """Returned immediately when an async job is created."""

    job_id: str
    status: JobStatus
