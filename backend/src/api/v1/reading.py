"""Adaptive reading endpoints.

    POST /api/v1/reading/generate
    GET  /api/v1/reading/{reading_id}

Implemented in task group 8 (adaptive reading). Generation is asynchronous:
the endpoint creates an ADAPTIVE_READING job and returns a job_id immediately.
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/reading", tags=["reading"])


@router.post("/generate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def generate_reading() -> dict[str, str]:
    """Create an adaptive-reading job and return a job_id (not yet implemented)."""
    return {"detail": "not_implemented"}


@router.get("/{reading_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_reading(reading_id: str) -> dict[str, str]:
    """Fetch a generated adaptive reading result (not yet implemented)."""
    return {"detail": "not_implemented"}
