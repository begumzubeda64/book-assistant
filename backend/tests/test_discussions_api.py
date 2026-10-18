"""API tests for the discussions router."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from src.api.dependencies import get_discussion_service
from src.core.config import Settings
from src.core.errors import NotFoundError
from src.core.security.cognito import AuthenticatedUser
from src.main import create_app
from src.models.conversation import (
    Conversation,
    Message,
    MessageRole,
    SourceCitation,
)


class FakeDiscussionService:
    def __init__(self) -> None:
        self.conversations: dict[str, Conversation] = {}

    async def create_conversation(
        self,
        user: AuthenticatedUser,
        book_id: str,
        title: str | None,
        persona: str | None = None,
    ) -> Conversation:
        conv = Conversation(
            user_id=user.user_id,
            conversation_id="c1",
            book_id=book_id,
            title=title,
            persona=persona,
        )
        self.conversations["c1"] = conv
        return conv

    async def get_conversation(
        self, user: AuthenticatedUser, conversation_id: str
    ) -> Conversation:
        conv = self.conversations.get(conversation_id)
        if conv is None or conv.user_id != user.user_id:
            raise NotFoundError(
                "Conversation not found", code="CONVERSATION_NOT_FOUND"
            )
        return conv

    async def post_message(
        self, user: AuthenticatedUser, conversation_id: str, question: str
    ) -> Message:
        await self.get_conversation(user, conversation_id)
        return Message(
            message_id="m1",
            role=MessageRole.ASSISTANT,
            content="grounded answer",
            citations=[SourceCitation(chapter_title="Chapter 1", page=1)],
        )


@pytest.fixture
def service() -> FakeDiscussionService:
    return FakeDiscussionService()


@pytest.fixture
def client(service: FakeDiscussionService) -> Iterator[TestClient]:
    settings = Settings(app_env="local", auth_allow_local_dev_user=True)
    app = create_app(settings)
    app.dependency_overrides[get_discussion_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client


def test_create_conversation(client: TestClient) -> None:
    response = client.post("/api/v1/discussions", json={"book_id": "b"})
    assert response.status_code == 201
    assert response.json()["conversation_id"] == "c1"


def test_post_message_returns_grounded_answer(client: TestClient) -> None:
    client.post("/api/v1/discussions", json={"book_id": "b"})
    response = client.post(
        "/api/v1/discussions/c1/messages", json={"question": "What is X?"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"] == "grounded answer"
    assert body["citations"][0]["chapter_title"] == "Chapter 1"


def test_post_message_rejects_empty_question(client: TestClient) -> None:
    client.post("/api/v1/discussions", json={"book_id": "b"})
    response = client.post(
        "/api/v1/discussions/c1/messages", json={"question": ""}
    )
    assert response.status_code == 422


def test_get_conversation(client: TestClient) -> None:
    client.post("/api/v1/discussions", json={"book_id": "b", "title": "T"})
    response = client.get("/api/v1/discussions/c1")
    assert response.status_code == 200
    assert response.json()["book_id"] == "b"


def test_get_missing_conversation_404(client: TestClient) -> None:
    response = client.get("/api/v1/discussions/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


def test_discussions_require_auth(service: FakeDiscussionService) -> None:
    settings = Settings(app_env="local", auth_allow_local_dev_user=False)
    app = create_app(settings)
    app.dependency_overrides[get_discussion_service] = lambda: service
    with TestClient(app) as anon:
        response = anon.post("/api/v1/discussions", json={"book_id": "b"})
    assert response.status_code == 401
