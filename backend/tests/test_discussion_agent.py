"""Tests for the discussion graph/agent and grounding behavior."""

from __future__ import annotations

from src.agents.discussion import nodes
from src.agents.discussion.agent import DiscussionAgent
from src.agents.shared.ports import RetrievedPassage


class FakeRetriever:
    def __init__(self, passages: list[RetrievedPassage]) -> None:
        self._passages = passages
        self.calls: list[dict[str, object]] = []

    def retrieve(
        self, *, user_id: str, book_id: str, query: str, top_k: int = 8
    ) -> list[RetrievedPassage]:
        self.calls.append(
            {"user_id": user_id, "book_id": book_id, "query": query}
        )
        return self._passages


class EchoGenerator:
    def __init__(self) -> None:
        self.last_prompt = ""

    def generate(self, *, prompt: str, max_words: int) -> str:
        self.last_prompt = prompt
        return "A grounded answer."


def _passages() -> list[RetrievedPassage]:
    return [
        RetrievedPassage(
            text="Chapter 2 discusses X.",
            chunk_id="b:p10:s0",
            chapter_title="Chapter 2",
            page=10,
        ),
        RetrievedPassage(
            text="Chapter 5 connects X to Y.",
            chunk_id="b:p40:s0",
            chapter_title="Chapter 5",
            page=40,
        ),
    ]


def test_agent_returns_answer_and_citations() -> None:
    retriever = FakeRetriever(_passages())
    agent = DiscussionAgent(retriever=retriever, generator=EchoGenerator())

    result = agent.answer(user_id="u1", book_id="b", question="How does X relate to Y?")

    assert result.answer == "A grounded answer."
    # Citations come only from retrieved passages (cross-chapter here).
    chapters = {c["chapter_title"] for c in result.citations}
    assert chapters == {"Chapter 2", "Chapter 5"}


def test_retrieval_is_user_and_book_scoped() -> None:
    retriever = FakeRetriever(_passages())
    agent = DiscussionAgent(retriever=retriever, generator=EchoGenerator())
    agent.answer(user_id="u1", book_id="bookZ", question="q")
    assert retriever.calls[0]["user_id"] == "u1"
    assert retriever.calls[0]["book_id"] == "bookZ"


def test_citations_never_fabricated_when_no_sources() -> None:
    retriever = FakeRetriever([])
    agent = DiscussionAgent(retriever=retriever, generator=EchoGenerator())
    result = agent.answer(user_id="u1", book_id="b", question="q")
    assert result.citations == []


def test_prompt_instructs_grounding_and_includes_context() -> None:
    gen = EchoGenerator()
    agent = DiscussionAgent(retriever=FakeRetriever(_passages()), generator=gen)
    agent.answer(
        user_id="u1",
        book_id="b",
        question="q",
        history=[("user", "earlier question"), ("assistant", "earlier answer")],
    )
    assert "ONLY using the source material" in gen.last_prompt
    assert "earlier question" in gen.last_prompt
    assert "b:p10:s0" in gen.last_prompt


def test_passages_to_citations_dedupes() -> None:
    passages = [
        RetrievedPassage(text="a", chapter_title="C1", page=1),
        RetrievedPassage(text="b", chapter_title="C1", page=1),
        RetrievedPassage(text="c", chapter_title="C2", page=2),
    ]
    citations = nodes.passages_to_citations(passages)
    assert len(citations) == 2
