"""Discussion agent entrypoint.

Unlike the ingestion and adaptive-reading agents (async, SQS-triggered), the
discussion agent is invoked directly for short interactive turns (design.md). It
runs the retrieve→generate graph and returns the grounded answer plus citations;
persistence is handled by the calling service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.agents.discussion.graph import build_discussion_graph
from src.agents.discussion.state import DiscussionState
from src.agents.shared.ports import GraphRAGRetrievalPort, TextGenerationPort


@dataclass
class DiscussionAnswer:
    answer: str
    citations: list[dict[str, object]]


class DiscussionAgentProtocol(Protocol):
    """The discussion-agent surface the service depends on.

    Satisfied by both the in-process DiscussionAgent and the API-side
    RemoteDiscussionAgent (which invokes the discussion AgentCore runtime).
    """

    def answer(
        self,
        *,
        user_id: str,
        book_id: str,
        question: str,
        history: list[tuple[str, str]] | None = None,
    ) -> DiscussionAnswer: ...


class RemoteDiscussionAgent:
    """API-side facade that runs discussion via the discussion AgentCore runtime.

    Keeps DiscussionService agnostic of transport: it calls ``.answer(...)`` the
    same way as the in-process agent, but the work (GraphRAG retrieval +
    generation through the MCP tools) happens in the isolated agent runtime. The
    API mints a signed scope token from the authenticated user_id so the tool
    tier authorizes the call; the API itself holds no Bedrock permissions.
    """

    def __init__(
        self, *, invoker: object, runtime_arn: str, scope_secret: str
    ) -> None:
        self._invoker = invoker
        self._runtime_arn = runtime_arn
        self._scope_secret = scope_secret

    def answer(
        self,
        *,
        user_id: str,
        book_id: str,
        question: str,
        history: list[tuple[str, str]] | None = None,
    ) -> DiscussionAnswer:
        from src.mcp_server.scope import mint_scope_token

        token = mint_scope_token(
            user_id=user_id, job_id="discussion", secret=self._scope_secret
        )
        result = self._invoker.invoke(  # type: ignore[attr-defined]
            self._runtime_arn,
            {
                "user_id": user_id,
                "book_id": book_id,
                "question": question,
                "history": [list(h) for h in (history or [])],
                "scope_token": token,
            },
        )
        return DiscussionAnswer(
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
        )


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
