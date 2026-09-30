"""Adaptive reading endpoints.

    POST /api/v1/reading/generate   -> create ADAPTIVE_READING job (async)
    GET  /api/v1/reading/{reading_id} -> fetch the generated reading

Generation runs off the request path: the endpoint creates a job and returns a
job_id immediately (requirement 4.7). The reading_id equals the job_id.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies import (
    CurrentUser,
    JobServiceDep,
    ReadingResultRepoDep,
    enforce_ai_rate_limit,
)
from src.core.errors import NotFoundError, ValidationAppError
from src.models.job import JobType
from src.schemas.jobs import JobCreatedResponse
from src.schemas.reading import ReadingGenerateRequest, ReadingResult

router = APIRouter(prefix="/reading", tags=["reading"])


@router.post(
    "/generate",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(enforce_ai_rate_limit("reading_generate"))],
)
async def generate_reading(
    user: CurrentUser,
    jobs: JobServiceDep,
    request: ReadingGenerateRequest,
) -> JobCreatedResponse:
    """Create an adaptive-reading job and return a job_id immediately."""
    try:
        request.validate_duration()
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    job = await jobs.create_and_enqueue(
        user_id=user.user_id,
        job_type=JobType.ADAPTIVE_READING,
        book_id=request.book_id,
        idempotency_key=(
            f"reading:{user.user_id}:{request.book_id}:{request.chapter_id}:"
            f"{request.duration_minutes}:{request.mode.value}:{request.focus.value}"
        ),
        chapter_id=request.chapter_id,
        target_duration=request.duration_minutes,
        mode=request.mode.value,
        focus=request.focus.value,
    )
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


@router.get("/{reading_id}", response_model=ReadingResult)
async def get_reading(
    user: CurrentUser,
    results: ReadingResultRepoDep,
    reading_id: str,
) -> ReadingResult:
    """Fetch a generated adaptive reading (scoped to the requesting user)."""
    payload = await results.get(user.user_id, reading_id)
    if payload is None:
        raise NotFoundError(
            "The requested reading could not be found", code="READING_NOT_FOUND"
        )
    return ReadingResult.model_validate(payload)
