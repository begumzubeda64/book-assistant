"""Tests for the agent-tier MCP client adapters.

Verify each adapter calls the right tool with the right arguments and never
sends user_id (the server derives it from the scope token), and that response
unwrapping handles FastMCP's structured/text shapes.
"""

from __future__ import annotations

import base64
from typing import Any

from src.agents.shared.mcp_client import (
    McpBookContent,
    McpContentStore,
    McpGraphRAGRetrieval,
    McpKnowledgeBase,
    McpReadingStore,
    McpTextGeneration,
    build_mcp_url,
)
from src.agents.shared.types import PreparedChunk, SourceRef


class FakeClient:
    """Records tool calls and returns a scripted result."""

    def __init__(self, result: Any = None) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return self.result


def test_build_mcp_url_encodes_arn() -> None:
    url = build_mcp_url(
        "eu-central-1", "arn:aws:bedrock-agentcore:eu-central-1:1:runtime/mcp-x"
    )
    assert url.startswith(
        "https://bedrock-agentcore.eu-central-1.amazonaws.com/runtimes/"
    )
    assert "arn%3Aaws%3Abedrock-agentcore" in url
    assert url.endswith("/invocations?qualifier=DEFAULT")


def test_content_store_decodes_and_omits_user_id() -> None:
    payload = base64.b64encode(b"%PDF-bytes").decode()
    client = FakeClient(result=payload)
    out = McpContentStore(client).fetch_pdf_bytes("u1", "uploads/u1/b.pdf")
    assert out == b"%PDF-bytes"
    name, args = client.calls[0]
    assert name == "get_authorized_content"
    assert args == {"object_key": "uploads/u1/b.pdf"}
    assert "user_id" not in args


def test_knowledge_base_sends_book_and_chunks_only() -> None:
    client = FakeClient(result="ij-1")
    chunk = PreparedChunk(
        chunk_id="c1", text="t", word_count=1, source=SourceRef(book_id="b1")
    )
    ref = McpKnowledgeBase(client).ingest_chunks(
        user_id="u1", book_id="b1", chunks=[chunk]
    )
    assert ref == "ij-1"
    name, args = client.calls[0]
    assert name == "ingest_to_knowledge_base"
    assert set(args) == {"book_id", "chunks"}
    assert "user_id" not in args


def test_book_content_parses_chunks() -> None:
    raw = [
        {
            "chunk_id": "c1",
            "text": "hello world",
            "word_count": 2,
            "source": {"book_id": "b1", "page": 1},
        }
    ]
    client = FakeClient(result=raw)
    chunks = McpBookContent(client).get_chunks(user_id="u1", book_id="b1")
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "c1"
    assert client.calls[0][0] == "get_book_content"


def test_text_generation_passes_prompt_and_budget() -> None:
    client = FakeClient(result="generated prose")
    out = McpTextGeneration(client).generate(prompt="p", max_words=100)
    assert out == "generated prose"
    assert client.calls[0] == ("generate_text", {"prompt": "p", "max_words": 100})


def test_reading_store_sends_reading_id_and_payload() -> None:
    client = FakeClient(result="s3://bucket/readings/u1/r1.json")
    loc = McpReadingStore(client).store_reading(
        user_id="u1", reading_id="r1", payload="{}"
    )
    assert loc.startswith("s3://")
    name, args = client.calls[0]
    assert name == "store_reading_result"
    assert set(args) == {"reading_id", "payload"}


def test_graphrag_parses_passages() -> None:
    raw = [{"text": "passage", "chunk_id": "c1", "page": 3}]
    client = FakeClient(result=raw)
    passages = McpGraphRAGRetrieval(client).retrieve(
        user_id="u1", book_id="b1", query="q"
    )
    assert len(passages) == 1
    assert passages[0].text == "passage"
    name, args = client.calls[0]
    assert name == "graphrag_retrieve"
    assert set(args) == {"book_id", "query", "top_k"}
