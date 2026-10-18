"""Adaptive-reading graph state."""

from __future__ import annotations

from typing import TypedDict

from src.agents.shared.types import PreparedChunk
from src.models.reading import ReadingFocus, ReadingMode


class ReadingState(TypedDict, total=False):
    """State threaded through the adaptive-reading graph."""

    # Inputs
    job_id: str
    user_id: str
    book_id: str
    chapter_id: str | None
    duration_minutes: int
    mode: ReadingMode
    focus: ReadingFocus

    # Populated by nodes
    budget_words: int
    chunks: list[PreparedChunk]
    selected: list[PreparedChunk]
    prompt: str
    content: str
    source_refs: list[dict[str, object]]
    result_location: str
