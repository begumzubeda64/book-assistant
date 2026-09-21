"""Async job status endpoints.

    GET /api/v1/jobs/{job_id}

Job status (QUEUED / PROCESSING / COMPLETED / FAILED) is surfaced here.
Implemented alongside the async job groups (6, 7, 8).
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_job(job_id: str) -> dict[str, str]:
    """Return the status/result location of an async job (not yet implemented)."""
    return {"detail": "not_implemented"}
