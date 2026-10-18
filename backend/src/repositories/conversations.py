"""Conversation repository (DynamoDB).

Table design: partition key ``user_id``, sort key ``conversation_id``. The
conversation and its messages are stored as a single item, which fits the MVP
access patterns (get/list a user's conversations, read messages, append a
message). Everything is user-scoped so a user can only access their own threads.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.models.conversation import Conversation, Message


class ConversationRepository(Protocol):
    async def create(self, conversation: Conversation) -> Conversation: ...

    async def get(self, user_id: str, conversation_id: str) -> Conversation | None: ...

    async def list_for_book(
        self, user_id: str, book_id: str
    ) -> list[Conversation]: ...

    async def append_messages(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[Message],
        *,
        summary: str | None = None,
        title: str | None = None,
    ) -> Conversation: ...


class DynamoDBConversationRepository:
    def __init__(self, table: Any) -> None:
        self._table = table

    async def create(self, conversation: Conversation) -> Conversation:
        self._table.put_item(
            Item=conversation.model_dump(mode="json", exclude_none=True),
            ConditionExpression="attribute_not_exists(conversation_id)",
        )
        return conversation

    async def get(
        self, user_id: str, conversation_id: str
    ) -> Conversation | None:
        response = self._table.get_item(
            Key={"user_id": user_id, "conversation_id": conversation_id}
        )
        item = response.get("Item")
        return Conversation.model_validate(item) if item else None

    async def list_for_book(
        self, user_id: str, book_id: str
    ) -> list[Conversation]:
        """Return the user's conversations for a book (newest first).

        No (user, book) index exists, so query the user's partition and filter.
        """
        response = self._table.query(
            KeyConditionExpression="user_id = :u",
            ExpressionAttributeValues={":u": user_id},
        )
        convos = [
            Conversation.model_validate(item)
            for item in (response.get("Items") or [])
            if item.get("book_id") == book_id
        ]
        convos.sort(key=lambda c: c.updated_at, reverse=True)
        return convos

    async def append_messages(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[Message],
        *,
        summary: str | None = None,
        title: str | None = None,
    ) -> Conversation:
        conversation = await self.get(user_id, conversation_id)
        if conversation is None:
            raise KeyError("conversation not found")
        conversation.messages.extend(messages)
        if summary is not None:
            conversation.summary = summary
        if title is not None:
            conversation.title = title
        from datetime import UTC, datetime

        conversation.updated_at = datetime.now(UTC)
        self._table.put_item(
            Item=conversation.model_dump(mode="json", exclude_none=True)
        )
        return conversation
