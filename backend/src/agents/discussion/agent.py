"""Discussion agent entrypoint.

Unlike the ingestion and adaptive-reading agents (async, SQS-triggered), the
discussion agent is invoked directly for short interactive turns (design.md). It
runs the retrieve→generate graph and returns the grounded answer plus citations;
persistence is handled by the calling service.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.agents.discussion.graph import build_discussion_graph
from src.agents.discussion.state import DiscussionState
from src.agents.shared.ports import GraphRAGRetrievalPort, TextGenerationPort


@dataclass
class DiscussionAnswer:
    answer: str
    citations: list[dict[str, object]]


class DiscussionAgent:
    def __init__(
        self,
        *,
        retriever: GraphRAGRetrievalPort,
        generator: TextGenerationPort,
    ) -> None:
        self._graph = build_discussion_graph(retriever, generator)

    def answer(
        self,
        *,
        user_id: str,
        book_id: str,
        question: str,
        history: list[tuple[str, str]] | None = None,
    ) -> DiscussionAnswer:
        state: DiscussionState = {
            "user_id": user_id,
            "book_id": book_id,
            "question": question,
            "history": history or [],
        }
        result = self._graph.invoke(state)
        return DiscussionAnswer(
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
        )
