"""Discussion conversation domain model.

A persisted question-and-answer thread about an authorized book. Owned by a
user; messages are grounded answers with source references. Keyed by
(user_id, conversation_id) so retrieval and access are user-scoped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class SourceCitation(BaseModel):
    """A source reference for a grounded answer (never fabricated)."""

    chunk_id: str | None = None
    chapter_title: str | None = None
    section: str | None = None
    page: int | None = None


class Message(BaseModel):
    """One turn in a conversation."""

    message_id: str
    role: MessageRole
    content: str
    citations: list[SourceCitation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class Conversation(BaseModel):
    """A discussion thread about a book."""

    user_id: str
    conversation_id: str
    book_id: str
    title: str | None = None
    messages: list[Message] = Field(default_factory=list)
    # Running summary of older turns, maintained once the thread grows past the
    # verbatim window, so long conversations stay within the model context
    # without losing earlier context (memory management).
    summary: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
