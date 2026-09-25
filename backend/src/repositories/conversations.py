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

    async def append_messages(
        self, user_id: str, conversation_id: str, messages: list[Message]
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

    async def append_messages(
        self, user_id: str, conversation_id: str, messages: list[Message]
    ) -> Conversation:
        conversation = await self.get(user_id, conversation_id)
        if conversation is None:
            raise KeyError("conversation not found")
        conversation.messages.extend(messages)
        from datetime import UTC, datetime

        conversation.updated_at = datetime.now(UTC)
        self._table.put_item(
            Item=conversation.model_dump(mode="json", exclude_none=True)
        )
        return conversation
