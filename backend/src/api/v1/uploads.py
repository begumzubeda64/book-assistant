"""Authorized PDF upload endpoints.

    POST /api/v1/uploads/presign
    POST /api/v1/books/{book_id}/ingest

Implemented in task groups 6 (upload) and 7 (ingestion).
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(tags=["uploads"])


@router.post("/uploads/presign", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def presign_upload() -> dict[str, str]:
    """Issue a short-lived presigned S3 upload URL (not yet implemented)."""
    return {"detail": "not_implemented"}


@router.post(
    "/books/{book_id}/ingest", status_code=status.HTTP_501_NOT_IMPLEMENTED
)
async def ingest_book(book_id: str) -> dict[str, str]:
    """Create a BOOK_INGESTION job for an uploaded book (not yet implemented)."""
    return {"detail": "not_implemented"}
