"""Reading progress domain model.

A user's current reading state for a book (design.md Progress). Keyed by
(user_id, book_id). Writes are idempotent and always ownership-scoped to the
authenticated user.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.models.reading import ReadingMode


def _now() -> datetime:
    return datetime.now(UTC)


class Progress(BaseModel):
    """A user's reading state for a single book."""

    user_id: str
    book_id: str
    chapter_id: str | None = None
    position: int = 0
    selected_duration: int | None = None
    selected_mode: ReadingMode | None = None
    completed: bool = False
    updated_at: datetime = Field(default_factory=_now)
