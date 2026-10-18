"""Tests for intent-based conversation titling (LLM-generated, short)."""

from __future__ import annotations

from src.agents.discussion import nodes
from src.agents.discussion.agent import DiscussionAgent, DiscussionAnswer
from src.agents.shared.ports import RetrievedPassage
from src.core.security.cognito import AuthenticatedUser
from src.models.conversation import Conversation


def test_clean_title_trims_quotes_and_caps_words() -> None:
    assert nodes.clean_title('"The Author\'s View"') == "The Author's View"
    assert nodes.clean_title("one two three four five six seven") == (
        "one two three four five"
    )
    assert nodes.clean_title("   ") == "Discussion"


class _TitleGenerator:
    """Echo generator that returns a scripted title for title prompts."""

    def __init__(self, title: str) -> None:
        self._title = title

    def generate(self, *, prompt: str, max_words: int) -> str:
        if prompt.endswith("TITLE:"):
            return self._title
        return "A grounded answer."


class _FakeRetriever:
    def retrieve(self, **_kwargs) -> list[RetrievedPassage]:
        return []


def test_agent_generates_short_title_on_opening_turns() -> None:
    agent = DiscussionAgent(
        retriever=_FakeRetriever(), generator=_TitleGenerator("Marriage And Society")
    )
    result = agent.answer(user_id="u1", book_id="b1", question="real topic?")
    assert result.title == "Marriage And Society"


def test_agent_stops_titling_after_opening_turns() -> None:
    agent = DiscussionAgent(
        retriever=_FakeRetriever(), generator=_TitleGenerator("Later Topic")
    )
    long_history = [
        ("user" if i % 2 == 0 else "assistant", f"turn {i}")
        for i in range(nodes.TITLE_REFRESH_TURNS + 2)
    ]
    # A real (non-generic) title already exists, so past the opening window it
    # should stabilize and not be regenerated.
    result = agent.answer(
        user_id="u1",
        book_id="b1",
        question="q",
        history=long_history,
        current_title="Established Topic",
    )
    assert result.title is None  # title has stabilized


def test_generic_title_keeps_refreshing_past_the_window() -> None:
    # Past the opening window, a stabilized real title would not refresh — but a
    # still-generic title ("General chat") must keep refreshing so a later topic
    # replaces it.
    agent = DiscussionAgent(
        retriever=_FakeRetriever(), generator=_TitleGenerator("Real Topic Now")
    )
    long_history = [
        ("user" if i % 2 == 0 else "assistant", f"turn {i}")
        for i in range(nodes.TITLE_REFRESH_TURNS + 2)
    ]
    result = agent.answer(
        user_id="u1",
        book_id="b1",
        question="a real topic?",
        history=long_history,
        current_title="General chat",
    )
    assert result.title == "Real Topic Now"


def test_is_generic_title() -> None:
    assert nodes.is_generic_title("General chat") is True
    assert nodes.is_generic_title("  discussion ") is True
    assert nodes.is_generic_title(None) is True
    assert nodes.is_generic_title("Marriage And Society") is False


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
    def __init__(self, title: str | None) -> None:
        self._title = title

    def answer(self, **_kwargs) -> DiscussionAnswer:
        return DiscussionAnswer(
            answer="ok", citations=[], updated_summary=None, title=self._title
        )


async def test_service_persists_agent_title() -> None:
    conv = Conversation(user_id="u1", conversation_id="c1", book_id="b1")
    repo = _FakeRepo(conv)
    from src.services.discussions import DiscussionService

    service = DiscussionService(repository=repo, agent=_FakeAgent("Key Themes"))  # type: ignore[arg-type]
    await service.post_message(
        AuthenticatedUser(user_id="u1"), "c1", "what are the themes?"
    )
    assert repo.title_set == "Key Themes"
