"""Discussion service.

Orchestrates conversations: create a thread, post a question (load prior
context, invoke the discussion agent, persist both the question and the grounded
answer), and read a thread back. Everything is scoped to the authenticated
user_id, so a user can only access their own conversations (requirement 1.3).
"""

from __future__ import annotations

import uuid

from src.agents.discussion.agent import DiscussionAgentProtocol
from src.core.errors import NotFoundError
from src.core.security.cognito import AuthenticatedUser
from src.models.conversation import (
    Conversation,
    Message,
    MessageRole,
    SourceCitation,
)
from src.repositories.conversations import ConversationRepository


class DiscussionService:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        agent: DiscussionAgentProtocol,
    ) -> None:
        self._repo = repository
        self._agent = agent

    async def create_conversation(
        self, user: AuthenticatedUser, book_id: str, title: str | None
    ) -> Conversation:
        conversation = Conversation(
            user_id=user.user_id,
            conversation_id=str(uuid.uuid4()),
            book_id=book_id,
            title=title,
        )
        return await self._repo.create(conversation)

    async def get_conversation(
        self, user: AuthenticatedUser, conversation_id: str
    ) -> Conversation:
        conversation = await self._repo.get(user.user_id, conversation_id)
        if conversation is None:
            raise NotFoundError(
                "Conversation not found", code="CONVERSATION_NOT_FOUND"
            )
        return conversation

    async def list_for_book(
        self, user: AuthenticatedUser, book_id: str
    ) -> list[Conversation]:
        """List the user's conversations for a book (newest first)."""
        return await self._repo.list_for_book(user.user_id, book_id)

    async def post_message(
        self, user: AuthenticatedUser, conversation_id: str, question: str
    ) -> Message:
        conversation = await self.get_conversation(user, conversation_id)

        history = [(m.role.value, m.content) for m in conversation.messages]
        # Pass both the running summary of older turns and the recent turns, so
        # the model has the full conversation context (memory management).
        result = self._agent.answer(
            user_id=user.user_id,
            book_id=conversation.book_id,
            question=question,
            history=history,
            summary=conversation.summary,
        )

        user_msg = Message(
            message_id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=question,
        )
        assistant_msg = Message(
            message_id=str(uuid.uuid4()),
            role=MessageRole.ASSISTANT,
            content=result.answer,
            citations=[
                SourceCitation.model_validate(c) for c in result.citations
            ],
        )
        await self._repo.append_messages(
            user.user_id,
            conversation_id,
            [user_msg, assistant_msg],
            summary=result.updated_summary,
            # Intent-based title from the agent (2-3 words), refreshed over the
            # opening turns; None after it stabilizes so it isn't overwritten.
            title=result.title,
        )
        return assistant_msg
