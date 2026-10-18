"""Adaptive reading API schemas.

Generation is asynchronous: the request creates an ADAPTIVE_READING job and the
API returns a job_id immediately (requirement 4.7). The result is fetched later
by reading_id.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field

from src.models.reading import (
    SUPPORTED_DURATIONS_MINUTES,
    ReadingFocus,
    ReadingMode,
)
from src.schemas.base import APIModel


class ReadingGenerateRequest(APIModel):
    """Configure an adaptive reading (3/5/10 min, mode, focus)."""

    book_id: str = Field(..., min_length=1)
    chapter_id: str | None = None
    duration_minutes: Annotated[int, Field(description="≈3, 5, or 10 minutes")]
    mode: ReadingMode
    focus: ReadingFocus = ReadingFocus.KEY_IDEAS

    def validate_duration(self) -> None:
        if self.duration_minutes not in SUPPORTED_DURATIONS_MINUTES:
            raise ValueError(
                f"duration_minutes must be one of {SUPPORTED_DURATIONS_MINUTES}"
            )


class ReadingSourceRef(APIModel):
    """A source reference retained in the generated reading (requirement 4.6)."""

    chapter_title: str | None = None
    section: str | None = None
    page: int | None = None


class ReadingSummary(APIModel):
    """A lightweight entry for listing a book's generated readings."""

    reading_id: str
    book_id: str
    mode: ReadingMode
    focus: ReadingFocus
    target_minutes: int
    created_at: datetime


class ReadingList(APIModel):
    items: list[ReadingSummary] = Field(default_factory=list)


class ReadingResult(APIModel):
    """A generated adaptive reading."""

    reading_id: str
    book_id: str
    chapter_id: str | None = None
    mode: ReadingMode
    focus: ReadingFocus
    target_minutes: int
    target_words: int
    actual_words: int
    content: str = Field(..., description="Coherent condensed prose")
    source_refs: list[ReadingSourceRef] = Field(default_factory=list)
    created_at: datetime
