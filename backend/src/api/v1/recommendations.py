"""Recommendation endpoints.

    GET /api/v1/recommendations

Implemented in task group 11 (recommendations).
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_recommendations() -> dict[str, str]:
    """Return recommended books with reasons (not yet implemented)."""
    return {"detail": "not_implemented"}
