"""Reading progress endpoints.

    GET /api/v1/progress/{book_id}
    PUT /api/v1/progress/{book_id}

Implemented in task group 10 (reading progress).
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/{book_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_progress(book_id: str) -> dict[str, str]:
    """Get saved reading progress for a book (not yet implemented)."""
    return {"detail": "not_implemented"}


@router.put("/{book_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def update_progress(book_id: str) -> dict[str, str]:
    """Save/update reading progress for a book (not yet implemented)."""
    return {"detail": "not_implemented"}
