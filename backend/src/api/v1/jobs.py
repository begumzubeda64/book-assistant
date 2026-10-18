"""Async job status endpoints.

    GET /api/v1/jobs/{job_id}

Surfaces job status (QUEUED / PROCESSING / COMPLETED / FAILED). Ownership is
enforced: a user can only read their own jobs (requirement 1.3).
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, JobServiceDep
from src.schemas.jobs import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    user: CurrentUser,
    service: JobServiceDep,
    job_id: str,
) -> JobResponse:
    """Return the status/result location of an async job."""
    job = await service.get_for_user(job_id, user)
    return JobResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        book_id=job.book_id,
        progress=job.progress,
        result_location=job.result_location,
        error_code=job.error_code,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )
