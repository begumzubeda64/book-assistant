"""Upload API schemas.

The user must confirm they are authorized to use the content before an upload is
accepted (requirement 3.1). The PDF is uploaded directly to S3 via a short-lived
presigned URL; it never travels through FastAPI (requirement 3.2).
"""

from __future__ import annotations

from pydantic import Field, field_validator

from src.schemas.base import APIModel

# Only PDFs are accepted for the MVP.
ALLOWED_CONTENT_TYPE = "application/pdf"


class PresignUploadRequest(APIModel):
    """Request a presigned URL to upload an authorized PDF."""

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(default=ALLOWED_CONTENT_TYPE)
    size_bytes: int = Field(..., gt=0, description="Declared file size in bytes")
    authorized_confirmation: bool = Field(
        ...,
        description="User confirms they are authorized to use this content",
    )

    @field_validator("authorized_confirmation")
    @classmethod
    def _must_confirm(cls, value: bool) -> bool:  # noqa: FBT001
        if value is not True:
            raise ValueError("authorization must be confirmed")
        return value


class PresignUploadResponse(APIModel):
    """A short-lived presigned S3 upload target."""

    book_id: str = Field(..., description="The id assigned to this upload")
    upload_url: str
    object_key: str
    method: str = "PUT"
    required_headers: dict[str, str] = Field(default_factory=dict)
    expires_in_seconds: int


class IngestRequest(APIModel):
    """Confirm an upload completed and start ingestion."""

    object_key: str = Field(..., min_length=1)
