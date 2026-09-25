"""GraphRAG discussion endpoints.

    POST /api/v1/discussions                       -> start a conversation
    POST /api/v1/discussions/{conversation_id}/messages -> ask a question
    GET  /api/v1/discussions/{conversation_id}     -> read the conversation

Answers are grounded in GraphRAG retrieval over the authorized book, with source
references. Conversations are scoped to the authenticated user (requirement 1.3).
"""

from __future__ import annotations

from fastapi import APIRouter, status

from src.api.dependencies import CurrentUser, DiscussionServiceDep
from src.schemas.discussions import (
    ConversationCreatedResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    PostMessageRequest,
)

router = APIRouter(prefix="/discussions", tags=["discussions"])


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
        user, request.book_id, request.title
    )
    return ConversationCreatedResponse(
        conversation_id=conversation.conversation_id,
        book_id=conversation.book_id,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
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
