"""Upload service.

Two steps:
1. presign  — validate the declared file (type/size) and that the user confirmed
   authorization, then issue a short-lived presigned S3 PUT for a private,
   per-user key. The PDF uploads directly to S3, never through FastAPI.
2. complete — validate the object belongs to the user (key prefix) and, when
   configured, that it actually exists in S3, then create the BOOK_INGESTION job
   and enqueue it. Idempotent per (user, object_key).
"""

from __future__ import annotations

import uuid

from src.core.errors import ForbiddenError, ValidationAppError
from src.core.security.cognito import AuthenticatedUser
from src.integrations.s3_storage import StoragePort, build_upload_key, owns_key
from src.models.job import Job, JobType
from src.schemas.uploads import (
    ALLOWED_CONTENT_TYPE,
    PresignUploadRequest,
    PresignUploadResponse,
)
from src.services.jobs import JobService

# 50 MB upload ceiling for the MVP.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PRESIGN_EXPIRY_SECONDS = 900  # 15 minutes


class UploadService:
    def __init__(
        self,
        *,
        storage: StoragePort,
        jobs: JobService,
        verify_object_exists: bool = False,
    ) -> None:
        self._storage = storage
        self._jobs = jobs
        self._verify_object_exists = verify_object_exists

    def presign(
        self, user: AuthenticatedUser, request: PresignUploadRequest
    ) -> PresignUploadResponse:
        if request.content_type != ALLOWED_CONTENT_TYPE:
            raise ValidationAppError("Only PDF uploads are supported")
        if request.size_bytes > MAX_UPLOAD_BYTES:
            raise ValidationAppError("File exceeds the maximum allowed size")
        # authorized_confirmation is enforced by the schema validator.

        book_id = str(uuid.uuid4())
        object_key = build_upload_key(user.user_id, book_id)
        url = self._storage.presign_put(
            object_key,
            content_type=ALLOWED_CONTENT_TYPE,
            expires_in=PRESIGN_EXPIRY_SECONDS,
        )
        return PresignUploadResponse(
            book_id=book_id,
            upload_url=url,
            object_key=object_key,
            required_headers={"Content-Type": ALLOWED_CONTENT_TYPE},
            expires_in_seconds=PRESIGN_EXPIRY_SECONDS,
        )

    async def complete_and_ingest(
        self, user: AuthenticatedUser, book_id: str, object_key: str
    ) -> Job:
        # Ownership by key prefix — never trust a client-supplied user id.
        if not owns_key(user.user_id, object_key):
            raise ForbiddenError("You do not have access to this upload")
        # The key must match the book id it claims to belong to.
        if object_key != build_upload_key(user.user_id, book_id):
            raise ValidationAppError("Upload key does not match the book id")
        if self._verify_object_exists and not self._storage.object_exists(
            object_key
        ):
            raise ValidationAppError("Uploaded object was not found")

        # Idempotent per uploaded object, so retries don't re-ingest.
        return await self._jobs.create_and_enqueue(
            user_id=user.user_id,
            job_type=JobType.BOOK_INGESTION,
            book_id=book_id,
            idempotency_key=f"ingest:{object_key}",
        )
