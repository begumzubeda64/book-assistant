"""Tests for context-based conversation titling from the first question."""

from __future__ import annotations

from src.core.security.cognito import AuthenticatedUser
from src.models.conversation import Conversation
from src.services.discussions import DiscussionService, _title_from_question


def test_title_from_short_question_is_verbatim() -> None:
    assert _title_from_question("What is the main argument?") == (
        "What is the main argument?"
    )


def test_title_from_long_question_is_trimmed_on_word_boundary() -> None:
    q = (
        "Do you think the society at those times had major roles in the "
        "socio-economic background of arranging marriages as described"
    )
    title = _title_from_question(q)
    assert len(title) <= 61  # 60 + ellipsis
    assert title.endswith("…")
    assert not title.endswith(" …")  # trimmed at a word boundary


class _FakeRepo:
    def __init__(self, conv: Conversation) -> None:
        self._conv = conv
        self.title_set: str | None = None

    async def get(self, user_id: str, conversation_id: str) -> Conversation:
        return self._conv

    async def append_messages(
        self, user_id, conversation_id, messages, *, summary=None, title=None
    ) -> Conversation:
        self.title_set = title
        return self._conv


class _FakeAgent:
    def answer(self, **_kwargs):
        from src.agents.discussion.agent import DiscussionAnswer

        return DiscussionAnswer(answer="ok", citations=[], updated_summary=None)


async def test_first_question_sets_conversation_title() -> None:
    conv = Conversation(user_id="u1", conversation_id="c1", book_id="b1")
    repo = _FakeRepo(conv)
    service = DiscussionService(repository=repo, agent=_FakeAgent())  # type: ignore[arg-type]
    user = AuthenticatedUser(user_id="u1")

    await service.post_message(user, "c1", "How does the author define freedom?")

    assert repo.title_set == "How does the author define freedom?"


async def test_title_not_overwritten_once_set() -> None:
    conv = Conversation(
        user_id="u1",
        conversation_id="c1",
        book_id="b1",
        title="Existing title",
    )
    # Simulate an existing message so it's not the first turn.
    from src.models.conversation import Message, MessageRole

    conv.messages.append(
        Message(message_id="m0", role=MessageRole.USER, content="earlier")
    )
    repo = _FakeRepo(conv)
    service = DiscussionService(repository=repo, agent=_FakeAgent())  # type: ignore[arg-type]
    await service.post_message(
        AuthenticatedUser(user_id="u1"), "c1", "a follow-up question"
    )
    # No new title passed (stays as the existing one).
    assert repo.title_set is None
