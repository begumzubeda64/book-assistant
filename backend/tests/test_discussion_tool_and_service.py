"""Tests for the GraphRAG retrieval tool, conversation repo, and service."""

from __future__ import annotations

from typing import Any

import pytest
from src.agents.discussion.agent import DiscussionAgent
from src.core.errors import NotFoundError
from src.core.security.cognito import AuthenticatedUser
from src.mcp_server.tools.graphrag import GraphRAGRetrievalTool
from src.models.conversation import Conversation, Message, MessageRole
from src.repositories.conversations import DynamoDBConversationRepository
from src.services.discussions import DiscussionService

USER = AuthenticatedUser(user_id="u1")


# --- GraphRAG retrieval tool: user + book scoping ---


class FakeAgentRuntime:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] = {}

    def retrieve(self, **kwargs: Any):
        self.last_kwargs = kwargs
        return {
            "retrievalResults": [
                {
                    "content": {"text": "passage text"},
                    "metadata": {
                        "chunk_id": "b:p1:s0",
                        "chapter_title": "Chapter 1",
                        "page": 1,
                    },
                    "score": 0.9,
                }
            ]
        }


def test_graphrag_tool_scopes_to_user_and_book() -> None:
    runtime = FakeAgentRuntime()
    tool = GraphRAGRetrievalTool(runtime, "kb-1")
    passages = tool.retrieve(user_id="u1", book_id="b", query="q")

    assert len(passages) == 1
    assert passages[0].chapter_title == "Chapter 1"
    # The retrieval filter constrains to this user and book.
    filt = runtime.last_kwargs["retrievalConfiguration"][
        "vectorSearchConfiguration"
    ]["filter"]["andAll"]
    keys = {list(f["equals"].values())[0] for f in filt}
    assert keys == {"user_id", "book_id"}


# --- Conversation repository (fake table) + service persistence ---


class FakeConvTable:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    def put_item(self, Item: dict[str, Any], ConditionExpression: str | None = None):  # noqa: N803
        self.items[(Item["user_id"], Item["conversation_id"])] = Item

    def get_item(self, Key: dict[str, Any]):  # noqa: N803
        item = self.items.get((Key["user_id"], Key["conversation_id"]))
        return {"Item": item} if item else {}


class StubAgent(DiscussionAgent):
    def __init__(self) -> None:  # bypass real graph
        pass

    def answer(self, **kwargs: Any):
        from src.agents.discussion.agent import DiscussionAnswer

        return DiscussionAnswer(
            answer="grounded",
            citations=[{"chapter_title": "Chapter 1", "page": 1}],
        )


@pytest.mark.asyncio
async def test_create_and_post_message_persists_turns() -> None:
    repo = DynamoDBConversationRepository(FakeConvTable())
    service = DiscussionService(repository=repo, agent=StubAgent())

    conv = await service.create_conversation(USER, "book1", "My thread")
    assistant = await service.post_message(USER, conv.conversation_id, "What is X?")

    assert assistant.role is MessageRole.ASSISTANT
    assert assistant.content == "grounded"
    assert assistant.citations[0].chapter_title == "Chapter 1"

    fetched = await service.get_conversation(USER, conv.conversation_id)
    # user question + assistant answer persisted.
    assert len(fetched.messages) == 2
    assert fetched.messages[0].role is MessageRole.USER


@pytest.mark.asyncio
async def test_get_missing_conversation_raises() -> None:
    repo = DynamoDBConversationRepository(FakeConvTable())
    service = DiscussionService(repository=repo, agent=StubAgent())
    with pytest.raises(NotFoundError):
        await service.get_conversation(USER, "nope")


@pytest.mark.asyncio
async def test_conversation_scoped_to_owner() -> None:
    table = FakeConvTable()
    repo = DynamoDBConversationRepository(table)
    service = DiscussionService(repository=repo, agent=StubAgent())
    conv = await service.create_conversation(USER, "book1", None)

    # A different user cannot read u1's conversation (different partition).
    other = AuthenticatedUser(user_id="u2")
    with pytest.raises(NotFoundError):
        await service.get_conversation(other, conv.conversation_id)


def test_conversation_model_roundtrip() -> None:
    conv = Conversation(
        user_id="u1",
        conversation_id="c1",
        book_id="b",
        messages=[Message(message_id="m1", role=MessageRole.USER, content="hi")],
    )
    dumped = conv.model_dump(mode="json")
    restored = Conversation.model_validate(dumped)
    assert restored.messages[0].content == "hi"
