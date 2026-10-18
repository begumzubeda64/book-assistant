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


@app.entrypoint
def handler(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore entrypoint: answer one discussion turn (grounded)."""
    configure_logging(get_settings().log_level)
    try:
        agent = _build_agent(payload.get("scope_token", ""))
        history = [tuple(h) for h in payload.get("history", [])]
        answer = agent.answer(
            user_id=payload["user_id"],
            book_id=payload["book_id"],
            question=payload["question"],
            history=history,  # type: ignore[arg-type]
            summary=payload.get("summary"),
        )
    except Exception:
        logger.exception("discussion_entrypoint_error")
        raise
    return {
        "answer": answer.answer,
        "citations": answer.citations,
        "updated_summary": answer.updated_summary,
    }


if __name__ == "__main__":  # pragma: no cover
    app.run()
