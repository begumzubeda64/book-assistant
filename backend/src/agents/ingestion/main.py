"""Ingestion agent entrypoint (AgentCore Runtime).

Receives a BOOK_INGESTION invocation (dispatched from SQS by the dispatcher),
builds MCP-client-backed tool ports, and runs the ingestion agent. The agent
holds NO AWS data permissions except its own job-status bookkeeping on the jobs
table; all content/KB access goes through the MCP tool server, authorized by the
signed scope token carried in the payload.

    python -m src.agents.ingestion.main    (via BedrockAgentCoreApp)
"""

from __future__ import annotations

import asyncio
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp

from src.agents.ingestion.agent import IngestionAgent
from src.agents.shared.mcp_client import (
    McpContentStore,
    McpKnowledgeBase,
    McpToolClient,
    build_mcp_url,
)
from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger
from src.repositories.jobs import DynamoDBJobRepository

logger = get_logger(__name__)
app = BedrockAgentCoreApp()


def _build_agent(scope_token: str) -> IngestionAgent:
    settings = get_settings()
    if not settings.mcp_runtime_arn:
        raise RuntimeError("MCP_RUNTIME_ARN is required for the ingestion agent")
    if not settings.jobs_table_name:
        raise RuntimeError("JOBS_TABLE_NAME is required for the ingestion agent")

    client = McpToolClient(
        url=build_mcp_url(settings.aws_region, settings.mcp_runtime_arn),
        region=settings.aws_region,
        scope_token=scope_token,
    )

    import boto3

    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    jobs = DynamoDBJobRepository(dynamodb.Table(settings.jobs_table_name))

    return IngestionAgent(
        content=McpContentStore(client),
        knowledge_base=McpKnowledgeBase(client),
        jobs=jobs,
    )


@app.entrypoint
def handler(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore entrypoint: process one BOOK_INGESTION job."""
    configure_logging(get_settings().log_level)
    scope_token = payload.get("scope_token", "")
    agent = _build_agent(scope_token)
    asyncio.run(agent.handle_message(payload))
    return {"status": "ok", "job_id": payload.get("job_id")}


if __name__ == "__main__":  # pragma: no cover
    app.run()
