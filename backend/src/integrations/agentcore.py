"""AgentCore invocation integration.

Invokes a Bedrock AgentCore runtime with a job payload. Used by the dispatcher
to bridge SQS messages to the matching agent runtime (AgentCore runtimes are not
a native SQS event source, so a consumer polls SQS and invokes them).

The boto3 client is injected for testability; the real data-plane call is
``bedrock-agentcore:invoke_agent_runtime(agentRuntimeArn=..., payload=...)``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Protocol

from src.core.config import Settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def _session_id(payload: dict[str, Any]) -> str:
    """AgentCore requires a runtimeSessionId of at least 33 characters.

    Derive a stable id from the job (so retries reuse the same session) and pad
    to the minimum length. Falls back to a random id when there is no job_id.
    """
    import uuid

    base = str(payload.get("job_id") or uuid.uuid4())
    # Pad deterministically to satisfy the >=33 char constraint.
    return (base + "-" + "0" * 33)[:48]


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
        from botocore.config import Config

        # Bound the blocking invoke so a cold/slow/hung agent run can't pin the
        # dispatcher for the full SQS visibility window. On timeout the invoke
        # raises, the message is left for redelivery, and the agent (which marks
        # the job PROCESSING/COMPLETED in DynamoDB and is idempotent) reconciles.
        client = boto3.client(
            "bedrock-agentcore",
            region_name=settings.aws_region,
            config=Config(
                read_timeout=120,
                connect_timeout=10,
                retries={"max_attempts": 0},
            ),
        )
        return cls(client)

    def invoke(self, runtime_arn: str, payload: dict[str, Any]) -> None:
        self._client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=_session_id(payload),
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
            runtimeSessionId=_session_id(payload),
            payload=json.dumps(payload).encode("utf-8"),
        )
        body = response.get("response")
        # boto3 returns a streaming body; normalize to bytes then JSON.
        if hasattr(body, "read"):
            body = body.read()
        if isinstance(body, bytes | bytearray):
            body = body.decode("utf-8")
        return json.loads(body) if body else {}

    def invoke_stream(
        self, runtime_arn: str, payload: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        """Invoke the runtime for an SSE stream, yielding decoded event dicts.

        Sets ``accept=text/event-stream`` so the runtime returns its generator
        output as SSE, then parses each ``data:`` line back into a dict. The
        runtime yields ``delta`` events then a ``final`` event (see the
        discussion agent entrypoint).
        """
        response = self._client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=_session_id(payload),
            payload=json.dumps(payload).encode("utf-8"),
            accept="text/event-stream",
        )
        body = response.get("response")
        if body is None:
            return
        # Iterate the streaming body line by line; SSE frames are "data: {...}".
        iterator = body.iter_lines() if hasattr(body, "iter_lines") else body
        for raw in iterator:
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes | bytearray) else raw
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if not data:
                continue
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                logger.warning("agentcore_stream_bad_frame")
                continue
