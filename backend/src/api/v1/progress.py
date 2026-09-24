"""Reading progress endpoints.

    GET /api/v1/progress/{book_id}   -> saved progress (continue-reading entry)
    PUT /api/v1/progress/{book_id}   -> idempotent upsert of progress

Progress is always scoped to the authenticated user; a user can only access
their own progress (requirement 1.3).
"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, ProgressServiceDep
from src.core.errors import NotFoundError
from src.schemas.progress import ProgressResponse, ProgressUpdate

router = APIRouter(prefix="/progress", tags=["progress"])


def _to_response(progress: object) -> ProgressResponse:
    return ProgressResponse.model_validate(progress, from_attributes=True)


@router.get("/{book_id}", response_model=ProgressResponse)
async def get_progress(
    user: CurrentUser,
    service: ProgressServiceDep,
    book_id: str,
) -> ProgressResponse:
    """Get saved reading progress for a book."""
    progress = await service.get_progress(user.user_id, book_id)
    if progress is None:
        raise NotFoundError(
            "No saved progress for this book", code="PROGRESS_NOT_FOUND"
        )
    return _to_response(progress)


@router.put("/{book_id}", response_model=ProgressResponse)
async def update_progress(
    user: CurrentUser,
    service: ProgressServiceDep,
    book_id: str,
    update: ProgressUpdate,
) -> ProgressResponse:
    """Save/update reading progress for a book (idempotent)."""
    progress = await service.save_progress(user.user_id, book_id, update)
    return _to_response(progress)
