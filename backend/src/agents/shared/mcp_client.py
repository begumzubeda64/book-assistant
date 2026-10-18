"""MCP client and port adapters for the agent tier.

Agents never touch AWS directly; they reach the allowlisted tools only through
the MCP tool server (its own AgentCore runtime). This module provides:

- a SigV4-signed streamable-HTTP MCP client to the MCP runtime, and
- adapter classes implementing the agent ports (ContentStorePort, etc.) by
  calling the corresponding MCP tool.

Security:
- Transport auth is AWS SigV4 (service ``bedrock-agentcore``): only a caller
  whose IAM role is granted InvokeAgentRuntime on the MCP runtime can connect.
- Every tool call carries the signed per-job scope token in the MCP ``_meta``;
  the server derives the trusted ``user_id`` from it and ignores any ``user_id``
  the client might send. The adapters therefore do not pass ``user_id`` at all.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from src.agents.shared.types import PreparedChunk

# AgentCore data-plane host + SigV4 service name.
_AGENTCORE_SERVICE = "bedrock-agentcore"


def build_mcp_url(region: str, runtime_arn: str) -> str:
    """AgentCore MCP invocation URL for a runtime ARN (DEFAULT qualifier)."""
    encoded = quote(runtime_arn, safe="")
    return (
        f"https://{_AGENTCORE_SERVICE}.{region}.amazonaws.com"
        f"/runtimes/{encoded}/invocations?qualifier=DEFAULT"
    )


class _SigV4Auth:
    """httpx.Auth that SigV4-signs each request with the task/runtime role."""

    def __init__(self, region: str, service: str = _AGENTCORE_SERVICE) -> None:
        import boto3
        from botocore.auth import SigV4Auth as _Botocore
        from botocore.awsrequest import AWSRequest

        self._region = region
        self._service = service
        self._session = boto3.Session()
        self._signer_cls = _Botocore
        self._aws_request_cls = AWSRequest

    def auth_flow(self, request: Any) -> Any:
        creds = self._session.get_credentials()
        if creds is None:
            raise RuntimeError("No AWS credentials available to sign MCP request")
        aws_req = self._aws_request_cls(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=dict(request.headers),
        )
        signer = self._signer_cls(
            creds.get_frozen_credentials(), self._service, self._region
        )
        signer.add_auth(aws_req)
        request.headers.update(dict(aws_req.headers))
        yield request


class McpToolClient:
    """Synchronous facade over the streamable-HTTP MCP client.

    Agent graphs are synchronous, so this runs each call on a short-lived event
    loop. The scope token is attached to every call as MCP ``_meta``.
    """

    def __init__(self, *, url: str, region: str, scope_token: str) -> None:
        self._url = url
        self._region = region
        self._scope_token = scope_token

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        import anyio

        return anyio.run(self._call_async, name, arguments)

    async def _call_async(self, name: str, arguments: dict[str, Any]) -> Any:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        auth = _SigV4Auth(self._region)
        async with (
            streamablehttp_client(self._url, auth=auth) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                name, arguments, meta={"scope_token": self._scope_token}
            )
            return _unwrap(result)


def _unwrap(result: Any) -> Any:
    """Return the tool's structured content, or the text payload parsed as JSON."""
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        # FastMCP wraps non-dict returns under a "result" key.
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except (ValueError, json.JSONDecodeError):
                return text
    return None


# --- Port adapters (one per agent capability) ------------------------------
#
# None of these pass user_id: the server derives it from the signed scope token.


class McpContentStore:
    """ContentStorePort via MCP."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def fetch_pdf_bytes(self, user_id: str, object_key: str) -> bytes:  # noqa: ARG002
        import base64

        b64 = self._client.call("get_authorized_content", {"object_key": object_key})
        return base64.b64decode(b64)


class McpKnowledgeBase:
    """KnowledgeBasePort via MCP."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def ingest_chunks(
        self, *, user_id: str, book_id: str, chunks: list[PreparedChunk]  # noqa: ARG002
    ) -> str:
        return self._client.call(
            "ingest_to_knowledge_base",
            {"book_id": book_id, "chunks": [c.model_dump() for c in chunks]},
        )


class McpBookContent:
    """BookContentPort via MCP."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def get_chunks(
        self, *, user_id: str, book_id: str, chapter_id: str | None = None  # noqa: ARG002
    ) -> list[PreparedChunk]:
        raw = self._client.call(
            "get_book_content", {"book_id": book_id, "chapter_id": chapter_id}
        )
        return [PreparedChunk.model_validate(c) for c in (raw or [])]


class McpTextGeneration:
    """TextGenerationPort via MCP."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def generate(self, *, prompt: str, max_words: int) -> str:
        return self._client.call(
            "generate_text", {"prompt": prompt, "max_words": max_words}
        )


class McpReadingStore:
    """ReadingStorePort via MCP."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def store_reading(self, *, user_id: str, reading_id: str, payload: str) -> str:  # noqa: ARG002
        return self._client.call(
            "store_reading_result", {"reading_id": reading_id, "payload": payload}
        )


class McpGraphRAGRetrieval:
    """GraphRAGRetrievalPort via MCP."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def retrieve(
        self, *, user_id: str, book_id: str, query: str, top_k: int = 8  # noqa: ARG002
    ) -> list[Any]:
        from src.agents.shared.ports import RetrievedPassage

        raw = self._client.call(
            "graphrag_retrieve", {"book_id": book_id, "query": query, "top_k": top_k}
        )
        return [RetrievedPassage.model_validate(p) for p in (raw or [])]
