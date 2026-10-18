"""Tests for streaming discussion answers (agent + service)."""

from __future__ import annotations

import pytest
from src.agents.discussion.agent import DiscussionAgent
from src.agents.shared.ports import RetrievedPassage
from src.core.security.cognito import AuthenticatedUser
from src.models.conversation import Conversation


class _StreamingGenerator:
    """Generator that streams fixed deltas, with a buffered fallback."""

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas

    def generate_stream(self, *, prompt: str, max_words: int):  # noqa: ANN001
        yield from self._deltas

    def generate(self, *, prompt: str, max_words: int) -> str:
        # Title/summary derivations call this; return something short.
        return "Title"


class _NonStreamingGenerator:
    def generate(self, *, prompt: str, max_words: int) -> str:
        return "Whole answer."


class _FakeRetriever:
    def retrieve(self, **_kwargs) -> list[RetrievedPassage]:
        return [RetrievedPassage(text="src", chunk_id="c1", page=1)]


def test_answer_stream_yields_deltas_then_final() -> None:
    agent = DiscussionAgent(
        retriever=_FakeRetriever(),
        generator=_StreamingGenerator(["Hello", " there", "!"]),
    )
    events = list(
        agent.answer_stream(user_id="u1", book_id="b1", question="hi?")
    )
    deltas = [e for e in events if e.type == "delta"]
    finals = [e for e in events if e.type == "final"]
    assert [d.text for d in deltas] == ["Hello", " there", "!"]
    assert len(finals) == 1
    assert finals[0].answer == "Hello there!"
    # Citations are derived from the retrieved passages.
    assert finals[0].citations and finals[0].citations[0]["page"] == 1


def test_answer_stream_falls_back_without_streaming_generator() -> None:
    agent = DiscussionAgent(
        retriever=_FakeRetriever(), generator=_NonStreamingGenerator()
    )
    events = list(
        agent.answer_stream(user_id="u1", book_id="b1", question="hi?")
    )
    # One delta carrying the whole answer, then a final.
    assert [e.type for e in events] == ["delta", "final"]
    assert events[-1].answer == "Whole answer."


class _FakeAgent:
    """Agent stub exposing answer_stream for the service test."""

    def answer_stream(self, **_kwargs):  # noqa: ANN003
        from src.agents.discussion.agent import DiscussionStreamEvent

        yield DiscussionStreamEvent(type="delta", text="Ans")
        yield DiscussionStreamEvent(type="delta", text="wer")
        yield DiscussionStreamEvent(
            type="final",
            answer="Answer",
            citations=[{"page": 2}],
            updated_summary=None,
            title="A Title",
        )


class _FakeRepo:
    def __init__(self, conv: Conversation) -> None:
        self._conv = conv
        self.appended: list = []

    async def get(self, user_id: str, conversation_id: str) -> Conversation:
        return self._conv

    async def append_messages(
        self, user_id, conversation_id, messages, *, summary=None, title=None
    ) -> Conversation:
        # Accumulate across calls (the user question is appended first, then the
        # assistant answer), mirroring the real repo.
        self.appended.extend(messages)
        self._conv.messages.extend(messages)
        if title is not None:
            self._conv.title = title
        return self._conv


@pytest.mark.anyio
async def test_service_stream_persists_and_emits_final() -> None:
    from src.services.discussions import DiscussionService

    conv = Conversation(user_id="u1", conversation_id="c1", book_id="b1")
    repo = _FakeRepo(conv)
    service = DiscussionService(repository=repo, agent=_FakeAgent())  # type: ignore[arg-type]

    events = []
    async for ev in service.post_message_stream(
        AuthenticatedUser(user_id="u1"), "c1", "what?"
    ):
        events.append(ev)

    deltas = [e for e in events if e["type"] == "delta"]
    finals = [e for e in events if e["type"] == "final"]
    assert "".join(d["text"] for d in deltas) == "Answer"
    assert len(finals) == 1
    assert finals[0]["title"] == "A Title"
    # Both the question and the grounded answer were persisted.
    assert len(repo.appended) == 2
    assert repo.appended[1].content == "Answer"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
