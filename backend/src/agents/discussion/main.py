"""Discussion agent entrypoint (AgentCore Runtime).

Unlike ingestion/adaptive (async, SQS-dispatched), the discussion agent is
invoked directly by the API for short interactive turns. GraphRAG retrieval and
generation go through the MCP tool server; the agent (and the API) hold no
direct Bedrock permissions. The API mints the signed scope token from the
authenticated user_id and passes it in the invocation payload.

Payload: {user_id, book_id, question, history?, scope_token}
Returns: {answer, citations}
"""

from __future__ import annotations

from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp

from src.agents.discussion.agent import DiscussionAgent
from src.agents.shared.mcp_client import (
    McpGraphRAGRetrieval,
    McpTextGeneration,
    McpToolClient,
    build_mcp_url,
)
from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger

logger = get_logger(__name__)
app = BedrockAgentCoreApp()


def _build_agent(scope_token: str) -> DiscussionAgent:
    settings = get_settings()
    if not settings.mcp_runtime_arn:
        raise RuntimeError("MCP_RUNTIME_ARN is required for the discussion agent")

    client = McpToolClient(
        url=build_mcp_url(settings.aws_region, settings.mcp_runtime_arn),
        region=settings.aws_region,
        scope_token=scope_token,
    )
    return DiscussionAgent(
        retriever=McpGraphRAGRetrieval(client),
        generator=McpTextGeneration(client),
    )


def _stream(payload: dict[str, Any]) -> Any:
    """Generator entrypoint: yield SSE-friendly dicts.

    Each ``{"type":"delta","text":...}`` carries an answer token; a final
    ``{"type":"final", answer, citations, updated_summary, title}`` closes the
    turn. BedrockAgentCoreApp serializes each yielded dict as an SSE ``data:``
    line automatically because this is a generator.
    """
    agent = _build_agent(payload.get("scope_token", ""))
    history = [tuple(h) for h in payload.get("history", [])]
    try:
        for ev in agent.answer_stream(
            user_id=payload["user_id"],
            book_id=payload["book_id"],
            question=payload["question"],
            history=history,  # type: ignore[arg-type]
            summary=payload.get("summary"),
            current_title=payload.get("current_title"),
            persona=payload.get("persona"),
        ):
            if ev.type == "delta":
                yield {"type": "delta", "text": ev.text}
            else:
                yield {
                    "type": "final",
                    "answer": ev.answer,
                    "citations": ev.citations,
                    "updated_summary": ev.updated_summary,
                    "title": ev.title,
                }
    except Exception:
        logger.exception("discussion_stream_error")
        yield {"type": "error"}


@app.entrypoint
def handler(payload: dict[str, Any]) -> Any:
    """AgentCore entrypoint: answer one discussion turn (grounded).

    Returns a generator (SSE stream) when ``stream`` is set; otherwise a single
    JSON dict. Both produce the same content — the stream yields deltas then a
    final event with the same fields as the buffered response.
    """
    configure_logging(get_settings().log_level)
    if payload.get("warmup"):
        return {"status": "warm"}
    if payload.get("stream"):
        # Returning a generator triggers the SDK's text/event-stream response.
        return _stream(payload)
    try:
        agent = _build_agent(payload.get("scope_token", ""))
        history = [tuple(h) for h in payload.get("history", [])]
        answer = agent.answer(
            user_id=payload["user_id"],
            book_id=payload["book_id"],
            question=payload["question"],
            history=history,  # type: ignore[arg-type]
            summary=payload.get("summary"),
            current_title=payload.get("current_title"),
            persona=payload.get("persona"),
        )
    except Exception:
        logger.exception("discussion_entrypoint_error")
        raise
    return {
        "answer": answer.answer,
        "citations": answer.citations,
        "updated_summary": answer.updated_summary,
        "title": answer.title,
    }


if __name__ == "__main__":  # pragma: no cover
    app.run()
