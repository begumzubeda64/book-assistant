"""Reading progress API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from src.models.reading import ReadingMode
from src.schemas.base import APIModel


class ProgressUpdate(APIModel):
    """Save/update reading progress for a book (idempotent upsert)."""

    chapter_id: str | None = None
    position: int = Field(default=0, ge=0)
    selected_duration: int | None = Field(default=None, ge=0)
    selected_mode: ReadingMode | None = None
    completed: bool = False


class ProgressResponse(APIModel):
    """A user's saved reading progress for a book."""

    book_id: str
    chapter_id: str | None = None
    position: int = 0
    selected_duration: int | None = None
    selected_mode: ReadingMode | None = None
    completed: bool = False
    updated_at: datetime
