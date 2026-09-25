"""Discussion API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from src.models.conversation import MessageRole
from src.schemas.base import APIModel


class CreateConversationRequest(APIModel):
    """Start a discussion about an authorized book."""

    book_id: str = Field(..., min_length=1)
    title: str | None = Field(default=None, max_length=200)


class PostMessageRequest(APIModel):
    """Ask a question in a conversation."""

    question: str = Field(..., min_length=1, max_length=2000)


class CitationResponse(APIModel):
    chunk_id: str | None = None
    chapter_title: str | None = None
    section: str | None = None
    page: int | None = None


class MessageResponse(APIModel):
    message_id: str
    role: MessageRole
    content: str
    citations: list[CitationResponse] = Field(default_factory=list)
    created_at: datetime


class ConversationResponse(APIModel):
    conversation_id: str
    book_id: str
    title: str | None = None
    messages: list[MessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConversationCreatedResponse(APIModel):
    conversation_id: str
    book_id: str
