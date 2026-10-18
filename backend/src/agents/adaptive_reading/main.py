"""Adaptive-reading agent entrypoint (AgentCore Runtime).

Receives an ADAPTIVE_READING invocation (dispatched from SQS), builds
MCP-client-backed tool ports, and runs the adaptive-reading agent. All book
content, generation, and result storage go through the MCP tool server; the
agent holds no direct AWS data permissions beyond its job-status bookkeeping.
"""

from __future__ import annotations

import asyncio
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp

from src.agents.adaptive_reading.agent import AdaptiveReadingAgent
from src.agents.shared.mcp_client import (
    McpBookContent,
    McpReadingStore,
    McpTextGeneration,
    McpToolClient,
    build_mcp_url,
)
from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.repositories.jobs import DynamoDBJobRepository

logger = get_logger(__name__)
app = BedrockAgentCoreApp()


def _build_agent(scope_token: str) -> AdaptiveReadingAgent:
    settings = get_settings()
    if not settings.mcp_runtime_arn:
        raise RuntimeError("MCP_RUNTIME_ARN is required for the adaptive agent")
    if not settings.jobs_table_name:
        raise RuntimeError("JOBS_TABLE_NAME is required for the adaptive agent")

    client = McpToolClient(
        url=build_mcp_url(settings.aws_region, settings.mcp_runtime_arn),
        region=settings.aws_region,
        scope_token=scope_token,
    )

    import boto3

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    jobs = DynamoDBJobRepository(dynamodb.Table(settings.jobs_table_name))

    return AdaptiveReadingAgent(
        content=McpBookContent(client),
        generator=McpTextGeneration(client),
        store=McpReadingStore(client),
        jobs=jobs,
    )


@app.entrypoint
def handler(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore entrypoint: process one ADAPTIVE_READING job."""
    configure_logging(get_settings().log_level)
    if payload.get("warmup"):
        return {"status": "warm"}
    try:
        scope_token = payload.get("scope_token", "")
        agent = _build_agent(scope_token)
        asyncio.run(agent.handle_message(payload))
    except Exception:
        logger.exception("adaptive_entrypoint_error")
        raise
    return {"status": "ok", "job_id": payload.get("job_id")}


if __name__ == "__main__":  # pragma: no cover
    app.run()
