"""AgentCore invocation integration.

Invokes a Bedrock AgentCore runtime with a job payload. Used by the dispatcher
to bridge SQS messages to the matching agent runtime (AgentCore runtimes are not
a native SQS event source, so a consumer polls SQS and invokes them).

The boto3 client is injected for testability; the real data-plane call is
``bedrock-agentcore:invoke_agent_runtime(agentRuntimeArn=..., payload=...)``.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class AgentInvokerPort(Protocol):
    def invoke(self, runtime_arn: str, payload: dict[str, Any]) -> None:
        """Invoke an agent runtime with a JSON payload (fire-and-forget)."""
        ...


class AgentCoreInvoker:
    """Invokes AgentCore runtimes via the bedrock-agentcore data plane."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> AgentCoreInvoker:
        import boto3

        client = boto3.client(
            "bedrock-agentcore", region_name=settings.aws_region
        )
        return cls(client)

    def invoke(self, runtime_arn: str, payload: dict[str, Any]) -> None:
        self._client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            payload=json.dumps(payload).encode("utf-8"),
        )
        logger.info(
            "agent_runtime_invoked",
            extra={"job_type": payload.get("job_type")},
        )


class AgentCoreResponseInvoker:
    """Request/response invoke of an AgentCore runtime (e.g. discussion).

    Unlike the fire-and-forget dispatcher invoke, this reads and returns the
    runtime's JSON response.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> AgentCoreResponseInvoker:
        import boto3

        client = boto3.client("bedrock-agentcore", region_name=settings.aws_region)
        return cls(client)

    def invoke(self, runtime_arn: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            payload=json.dumps(payload).encode("utf-8"),
        )
        body = response.get("response")
        # boto3 returns a streaming body; normalize to bytes then JSON.
        if hasattr(body, "read"):
            body = body.read()
        if isinstance(body, bytes | bytearray):
            body = body.decode("utf-8")
        return json.loads(body) if body else {}
