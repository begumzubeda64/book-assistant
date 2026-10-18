"""Tests that MCP tools derive user_id from the signed scope token only.

These verify the security property: a caller cannot influence which user's data
a tool touches via arguments — the user_id always comes from the verified scope
token in the request _meta. A tool run without a valid token fails closed.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest
from src.agents.shared.types import PreparedChunk, SourceRef
from src.mcp_server.scope import ScopeError, mint_scope_token
from src.mcp_server.server import ToolBundle, create_mcp_server

_SECRET = "server-test-secret"


class _RecordingContent:
    def __init__(self) -> None:
        self.seen_user: str | None = None

    def fetch_pdf_bytes(self, user_id: str, object_key: str) -> bytes:  # noqa: ARG002
        self.seen_user = user_id
        return b"%PDF-data"


class _RecordingGraphRAG:
    def __init__(self) -> None:
        self.seen_user: str | None = None

    def retrieve(self, *, user_id: str, book_id: str, query: str, top_k: int = 8):  # noqa: ARG002
        self.seen_user = user_id
        return []


def _bundle(content: Any = None, graphrag: Any = None) -> ToolBundle:
    return ToolBundle(
        content=content or _RecordingContent(),
        knowledge_base=object(),  # type: ignore[arg-type]
        book_content=object(),  # type: ignore[arg-type]
        generation=object(),  # type: ignore[arg-type]
        reading_store=object(),  # type: ignore[arg-type]
        graphrag=graphrag or _RecordingGraphRAG(),
    )


class _FakeMeta:
    def __init__(self, scope_token: str) -> None:
        self.model_extra = {"scope_token": scope_token}


class _FakeRequestContext:
    def __init__(self, scope_token: str) -> None:
        self.meta = _FakeMeta(scope_token)


class _FakeCtx:
    def __init__(self, scope_token: str) -> None:
        self.request_context = _FakeRequestContext(scope_token)


def _tool(server: Any, name: str):
    """Fetch the raw registered callable for a tool by name."""
    # FastMCP stores tools in a manager; fall back to attribute scan.
    manager = server._tool_manager
    tool = manager.get_tool(name)
    return tool.fn


def test_tool_uses_scoped_user_not_arguments() -> None:
    content = _RecordingContent()
    server = create_mcp_server(_bundle(content=content), scope_secret=_SECRET)
    token = mint_scope_token(user_id="real-user", job_id="j1", secret=_SECRET)

    fn = _tool(server, "get_authorized_content")
    result = fn(object_key="uploads/real-user/b.pdf", ctx=_FakeCtx(token))

    assert base64.b64decode(result) == b"%PDF-data"
    # The user_id came from the token, not any argument.
    assert content.seen_user == "real-user"


def test_tool_without_token_fails_closed() -> None:
    server = create_mcp_server(_bundle(), scope_secret=_SECRET)
    fn = _tool(server, "graphrag_retrieve")
    with pytest.raises(ScopeError):
        fn(book_id="b", query="q", ctx=_FakeCtx(""))


def test_tool_with_forged_token_fails_closed() -> None:
    server = create_mcp_server(_bundle(), scope_secret=_SECRET)
    bad = mint_scope_token(user_id="attacker", job_id="j1", secret="wrong-secret")
    fn = _tool(server, "graphrag_retrieve")
    with pytest.raises(ScopeError):
        fn(book_id="b", query="q", ctx=_FakeCtx(bad))


def test_graphrag_tool_scopes_to_token_user() -> None:
    graphrag = _RecordingGraphRAG()
    server = create_mcp_server(_bundle(graphrag=graphrag), scope_secret=_SECRET)
    token = mint_scope_token(user_id="owner", job_id="j1", secret=_SECRET)
    fn = _tool(server, "graphrag_retrieve")
    fn(book_id="b", query="q", ctx=_FakeCtx(token))
    assert graphrag.seen_user == "owner"


_ = PreparedChunk, SourceRef  # keep imports for potential extension
