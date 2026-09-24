"""Shared agent-tier domain types."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Provenance for a chunk, preserved through ingestion for later citation."""

    book_id: str
    chapter_id: str | None = None
    chapter_title: str | None = None
    section: str | None = None
    page: int | None = None


class PreparedChunk(BaseModel):
    """A prepared, ingestion-ready unit of book content with provenance."""

    chunk_id: str
    text: str
    source: SourceRef
    word_count: int = Field(default=0, ge=0)
