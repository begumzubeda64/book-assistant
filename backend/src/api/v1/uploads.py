"""Authorized PDF upload endpoints.

    POST /api/v1/uploads/presign        -> presigned S3 URL (auth confirmed)
    POST /api/v1/books/{book_id}/ingest -> create BOOK_INGESTION job

The PDF is uploaded directly to S3 via the presigned URL and never travels
through FastAPI (requirement 3.2).
"""

from __future__ import annotations

from fastapi import APIRouter, status

from src.api.dependencies import CurrentUser, UploadServiceDep
from src.schemas.jobs import JobCreatedResponse
from src.schemas.uploads import (
    IngestRequest,
    PresignUploadRequest,
    PresignUploadResponse,
)

router = APIRouter(tags=["uploads"])


@router.post(
    "/uploads/presign",
    response_model=PresignUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def presign_upload(
    user: CurrentUser,
    service: UploadServiceDep,
    request: PresignUploadRequest,
) -> PresignUploadResponse:
    """Issue a short-lived presigned S3 upload URL for an authorized PDF."""
    return service.presign(user, request)


@router.post(
    "/books/{book_id}/ingest",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_book(
    user: CurrentUser,
    service: UploadServiceDep,
    book_id: str,
    request: IngestRequest,
) -> JobCreatedResponse:
    """Confirm an upload completed and create a BOOK_INGESTION job."""
    job = await service.complete_and_ingest(user, book_id, request.object_key)
    return JobCreatedResponse(job_id=job.job_id, status=job.status)
