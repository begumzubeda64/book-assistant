"""GraphRAG discussion endpoints.

    POST /api/v1/discussions                       -> start a conversation
    POST /api/v1/discussions/{conversation_id}/messages -> ask a question
    GET  /api/v1/discussions/{conversation_id}     -> read the conversation

Answers are grounded in GraphRAG retrieval over the authorized book, with source
references. Conversations are scoped to the authenticated user (requirement 1.3).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from src.agents.discussion.personas import DEFAULT_PERSONA, all_profiles
from src.api.dependencies import (
    CurrentUser,
    DiscussionServiceDep,
    enforce_ai_rate_limit,
)
from src.schemas.discussions import (
    ConversationCreatedResponse,
    ConversationList,
    ConversationResponse,
    ConversationSummary,
    CreateConversationRequest,
    MessageResponse,
    PersonaList,
    PersonaOption,
    PostMessageRequest,
)

router = APIRouter(prefix="/discussions", tags=["discussions"])


@router.get("/personas", response_model=PersonaList)
async def list_personas() -> PersonaList:
    """List the selectable discussion personas (voice/style options)."""
    return PersonaList(
        items=[
            PersonaOption(id=p.persona.value, label=p.label, description=p.description)
            for p in all_profiles()
        ],
        default=DEFAULT_PERSONA.value,
    )


@router.get("", response_model=ConversationList)
async def list_discussions(
    user: CurrentUser,
    service: DiscussionServiceDep,
    book_id: Annotated[str, Query(min_length=1)],
) -> ConversationList:
    """List the user's conversations for a book (newest first)."""
    convos = await service.list_for_book(user, book_id)
    return ConversationList(
        items=[
            ConversationSummary(
                conversation_id=c.conversation_id,
                book_id=c.book_id,
                title=c.title,
                persona=c.persona,
                message_count=len(c.messages),
                updated_at=c.updated_at,
            )
            for c in convos
        ]
    )


@router.post(
    "", response_model=ConversationCreatedResponse, status_code=status.HTTP_201_CREATED
)
async def create_discussion(
    user: CurrentUser,
    service: DiscussionServiceDep,
    request: CreateConversationRequest,
) -> ConversationCreatedResponse:
    """Start a discussion conversation for a book."""
    conversation = await service.create_conversation(
        user, request.book_id, request.title, request.persona
    )
    return ConversationCreatedResponse(
        conversation_id=conversation.conversation_id,
        book_id=conversation.book_id,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_ai_rate_limit("discussion_message"))],
)
async def post_message(
    user: CurrentUser,
    service: DiscussionServiceDep,
    conversation_id: str,
    request: PostMessageRequest,
) -> MessageResponse:
    """Ask a question and get a grounded answer with source references."""
    answer = await service.post_message(user, conversation_id, request.question)
    return MessageResponse.model_validate(answer, from_attributes=True)


@router.post(
    "/{conversation_id}/messages/stream",
    dependencies=[Depends(enforce_ai_rate_limit("discussion_message"))],
)
async def post_message_stream(
    user: CurrentUser,
    service: DiscussionServiceDep,
    conversation_id: str,
    request: PostMessageRequest,
) -> StreamingResponse:
    """Stream a grounded answer as Server-Sent Events.

    Emits ``data: {"type":"delta","text":...}`` frames as tokens arrive, then a
    final ``data: {"type":"final", message_id, title, citations}``. The full
    message is persisted server-side when generation completes, so navigating
    away does not lose the answer (it appears on return from the stored thread).
    """

    async def event_stream() -> AsyncIterator[bytes]:
        # Flush an initial comment so the connection opens immediately and any
        # intermediary starts streaming rather than buffering for first bytes.
        yield b": open\n\n"
        try:
            async for event in service.post_message_stream(
                user, conversation_id, request.question
            ):
                yield f"data: {json.dumps(event)}\n\n".encode()
        except Exception:
            yield b'data: {"type":"error"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_discussion(
    user: CurrentUser,
    service: DiscussionServiceDep,
    conversation_id: str,
) -> ConversationResponse:
    """Fetch a conversation and its messages."""
    conversation = await service.get_conversation(user, conversation_id)
    return ConversationResponse.model_validate(
        conversation, from_attributes=True
    )
