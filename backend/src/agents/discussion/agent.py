"""Discussion agent entrypoint.

Unlike the ingestion and adaptive-reading agents (async, SQS-triggered), the
discussion agent is invoked directly for short interactive turns (design.md). It
runs the retrieve→generate graph and returns the grounded answer plus citations;
persistence is handled by the calling service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.agents.shared.ports import GraphRAGRetrievalPort, TextGenerationPort

# NOTE: the LangGraph graph is imported lazily inside DiscussionAgent.__init__.
# The API image does NOT install the `agents` extra (langgraph/mcp/pypdf), and
# it only ever uses RemoteDiscussionAgent / the protocol from this module — so
# importing this module must not require langgraph.


@dataclass
class DiscussionAnswer:
    answer: str
    citations: list[dict[str, object]]
    # Updated running summary of older turns (memory management); None when the
    # thread is short enough that no summary is needed yet.
    updated_summary: str | None = None
    # A short, intent-based title (2-3 words), (re)generated during the opening
    # turns; None when the title shouldn't change this turn.
    title: str | None = None


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
        summary: str | None = None,
        current_title: str | None = None,
        persona: str | None = None,
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
        summary: str | None = None,
        current_title: str | None = None,
        persona: str | None = None,
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
                "summary": summary,
                "current_title": current_title,
                "persona": persona,
                "scope_token": token,
            },
        )
        return DiscussionAnswer(
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
            updated_summary=result.get("updated_summary"),
            title=result.get("title"),
        )


class DiscussionAgent:
    def __init__(
        self,
        *,
        retriever: GraphRAGRetrievalPort,
        generator: TextGenerationPort,
    ) -> None:
        from src.agents.discussion.graph import build_discussion_graph

        self._graph = build_discussion_graph(retriever, generator)
        self._generator = generator

    def answer(
        self,
        *,
        user_id: str,
        book_id: str,
        question: str,
        history: list[tuple[str, str]] | None = None,
        summary: str | None = None,
        current_title: str | None = None,
        persona: str | None = None,
    ) -> DiscussionAnswer:
        from src.agents.discussion import nodes
        from src.agents.discussion.personas import profile_for

        turns = history or []
        state: dict[str, object] = {
            "user_id": user_id,
            "book_id": book_id,
            "question": question,
            "history": turns,
            "summary": summary,
            "persona_voice": profile_for(persona).voice,
        }
        result = self._graph.invoke(state)

        # Memory management: once the thread exceeds the verbatim window, fold
        # the aged-out turns into a concise running summary so future turns stay
        # within the context window without losing earlier context.
        updated_summary = summary
        if len(turns) > nodes.SUMMARY_THRESHOLD:
            aged_out = turns[: -nodes.CONTEXT_TURN_LIMIT]
            if aged_out:
                summary_prompt = nodes.build_summary_prompt(summary, aged_out)
                updated_summary = self._generator.generate(
                    prompt=summary_prompt, max_words=200
                ).strip()

        # Intent-based title. (Re)generate during the opening turns so a casual
        # opener gets replaced once a real topic emerges. Also keep regenerating
        # for as long as the current title is still a placeholder ("General
        # chat"/none), so a topic that appears later still replaces it — i.e.
        # "replace the title if context was not enough" earlier.
        title: str | None = None
        if (
            len(turns) <= nodes.TITLE_REFRESH_TURNS
            or nodes.is_generic_title(current_title)
        ):
            title_prompt = nodes.build_title_prompt(turns, question)
            title = nodes.clean_title(
                self._generator.generate(prompt=title_prompt, max_words=8)
            )

        return DiscussionAnswer(
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
            updated_summary=updated_summary,
            title=title,
        )
