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
from collections.abc import Iterator
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


def _make_sigv4_auth(region: str, service: str = _AGENTCORE_SERVICE) -> Any:
    """Build an httpx.Auth that SigV4-signs each request with the runtime role.

    Defined as a factory so httpx is imported lazily and the returned object is a
    genuine httpx.Auth subclass (httpx validates auth via isinstance).
    """
    import boto3
    import httpx
    from botocore.auth import SigV4Auth as BotocoreSigV4
    from botocore.awsrequest import AWSRequest

    session = boto3.Session()

    class _SigV4Auth(httpx.Auth):
        # Signing needs the request body, so httpx must buffer it first.
        requires_request_body = True

        def auth_flow(self, request: httpx.Request) -> Any:
            creds = session.get_credentials()
            if creds is None:
                raise RuntimeError("No AWS credentials available to sign MCP request")
            aws_req = AWSRequest(
                method=request.method,
                url=str(request.url),
                data=request.content,
                headers=dict(request.headers),
            )
            BotocoreSigV4(
                creds.get_frozen_credentials(), service, region
            ).add_auth(aws_req)
            request.headers.update(dict(aws_req.headers))
            yield request

    return _SigV4Auth()


class McpToolClient:
    """Synchronous facade over the streamable-HTTP MCP client.

    Agent graphs are synchronous, so this runs each call on a short-lived event
    loop. The scope token is attached to every call as MCP ``_meta``.
    """

    def __init__(self, *, url: str, region: str, scope_token: str) -> None:
        self._url = url
        self._region = region
        self._scope_token = scope_token

    def with_scope_token(self, scope_token: str) -> McpToolClient:
        """Return a copy bound to a different per-request scope token."""
        return McpToolClient(
            url=self._url, region=self._region, scope_token=scope_token
        )

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        import asyncio

        coro = self._call_async(name, arguments)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop: safe to drive one directly.
            return asyncio.run(coro)
        # Called from within a running loop (the agent's asyncio.run): run the
        # async MCP call on a fresh loop in a worker thread to avoid nesting.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    async def _call_async(self, name: str, arguments: dict[str, Any]) -> Any:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        auth = _make_sigv4_auth(self._region)
        async with (
            streamablehttp_client(self._url, auth=auth) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                name, arguments, meta={"scope_token": self._scope_token}
            )
            return _unwrap(result)

    def call_stream(
        self, name: str, arguments: dict[str, Any]
    ) -> Iterator[str]:
        """Call a streaming tool, yielding each progress ``message`` delta.

        The tool reports token deltas via MCP progress notifications; we forward
        them to a thread-safe queue and yield them as they arrive. The MCP call
        runs on its own event loop in a worker thread so the (synchronous) agent
        graph can iterate the deltas. A sentinel marks completion.
        """
        import queue
        import threading

        q: queue.Queue[tuple[str, Any]] = queue.Queue()

        async def _run() -> None:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async def _on_progress(
                progress: float, total: float | None, message: str | None
            ) -> None:
                if message:
                    q.put(("delta", message))

            auth = _make_sigv4_auth(self._region)
            try:
                async with (
                    streamablehttp_client(self._url, auth=auth) as (read, write, _),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    result = await session.call_tool(
                        name,
                        arguments,
                        meta={"scope_token": self._scope_token},
                        progress_callback=_on_progress,
                    )
                # The tool ALSO returns the complete text. Progress
                # notifications (our live deltas) may not survive the AgentCore
                # MCP transport (the server->client GET SSE channel can 405), so
                # the final return value is the source of truth for the answer.
                final_text = _unwrap(result)
                q.put(("final", final_text if isinstance(final_text, str) else ""))
            except Exception as exc:  # surfaced to the consumer
                q.put(("error", exc))

        def _thread() -> None:
            import asyncio

            asyncio.run(_run())

        worker = threading.Thread(target=_thread, daemon=True)
        worker.start()
        delivered = ""
        while True:
            kind, value = q.get()
            if kind == "delta":
                delivered += value
                yield value
            elif kind == "error":
                worker.join(timeout=1)
                raise value
            else:  # final: reconcile against the complete returned text
                worker.join(timeout=1)
                final_text = value or ""
                if not final_text:
                    return
                # Emit whatever of the complete answer wasn't already delivered
                # as live deltas, so the answer is never empty or truncated even
                # if progress notifications didn't arrive.
                if final_text.startswith(delivered):
                    remainder = final_text[len(delivered) :]
                    if remainder:
                        yield remainder
                elif not delivered:
                    yield final_text
                return


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
        return str(
            self._client.call(
                "ingest_to_knowledge_base",
                {"book_id": book_id, "chunks": [c.model_dump() for c in chunks]},
            )
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
        return str(
            self._client.call(
                "generate_text", {"prompt": prompt, "max_words": max_words}
            )
        )

    def generate_stream(self, *, prompt: str, max_words: int) -> Iterator[str]:
        """Stream generation deltas from the MCP ``generate_text_stream`` tool."""
        yield from self._client.call_stream(
            "generate_text_stream", {"prompt": prompt, "max_words": max_words}
        )


class McpReadingStore:
    """ReadingStorePort via MCP."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def store_reading(self, *, user_id: str, reading_id: str, payload: str) -> str:  # noqa: ARG002
        return str(
            self._client.call(
                "store_reading_result",
                {"reading_id": reading_id, "payload": payload},
            )
        )


class McpKnowledgeBaseDeleter:
    """Removes a book's KB data via the MCP tool (KnowledgeBaseDeleter port)."""

    def __init__(self, client: McpToolClient) -> None:
        self._client = client

    def delete_book(self, *, user_id: str, book_id: str) -> int:  # noqa: ARG002
        result = self._client.call(
            "delete_book_from_knowledge_base", {"book_id": book_id}
        )
        try:
            return int(result)
        except (TypeError, ValueError):
            return 0


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
