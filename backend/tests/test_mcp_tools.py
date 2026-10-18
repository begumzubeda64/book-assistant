"""Tests for the MCP tools (content access + KB ingestion) via fake AWS clients."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from src.agents.shared.types import PreparedChunk, SourceRef
from src.core.errors import ForbiddenError
from src.mcp_server.tools.content import ContentTool
from src.mcp_server.tools.knowledge_base import KnowledgeBaseTool, chunk_prefix


class FakeS3:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = objects or {}
        self.puts: list[dict[str, Any]] = []

    def get_object(self, Bucket: str, Key: str):  # noqa: N803
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, **kwargs: Any):
        self.puts.append(kwargs)


class FakeBedrockAgent:
    def __init__(self) -> None:
        self.ingestion_calls = 0

    def start_ingestion_job(self, **kwargs: Any):
        self.ingestion_calls += 1
        return {"ingestionJob": {"ingestionJobId": "ij-123"}}


def test_content_tool_returns_bytes_for_owner() -> None:
    key = "uploads/u1/book1.pdf"
    s3 = FakeS3({key: b"%PDF-fake"})
    tool = ContentTool(s3, "uploads-bucket")
    assert tool.fetch_pdf_bytes("u1", key) == b"%PDF-fake"


def test_content_tool_denies_foreign_key() -> None:
    tool = ContentTool(FakeS3(), "uploads-bucket")
    with pytest.raises(ForbiddenError):
        tool.fetch_pdf_bytes("u1", "uploads/other/book1.pdf")


def test_kb_tool_writes_chunks_and_starts_ingestion() -> None:
    s3 = FakeS3()
    bedrock = FakeBedrockAgent()
    tool = KnowledgeBaseTool(
        s3_client=s3,
        bedrock_agent_client=bedrock,
        chunk_bucket="kb-chunks",
        knowledge_base_id="kb-1",
        data_source_id="ds-1",
    )
    chunks = [
        PreparedChunk(
            chunk_id="book1:p1:s0",
            text="hello",
            word_count=1,
            source=SourceRef(book_id="book1", page=1),
        )
    ]

    ref = tool.ingest_chunks(user_id="u1", book_id="book1", chunks=chunks)

    assert ref == "ij-123"
    assert bedrock.ingestion_calls == 1
    # Each chunk writes a text document + a filterable metadata sidecar.
    assert len(s3.puts) == 2
    by_key = {p["Key"]: p for p in s3.puts}
    prefix = chunk_prefix("u1", "book1")
    text_key = f"{prefix}book1:p1:s0.txt"
    sidecar_key = f"{text_key}.metadata.json"
    assert text_key in by_key
    assert sidecar_key in by_key
    # Document body is the chunk text (not a JSON wrapper).
    assert by_key[text_key]["Body"] == b"hello"
    # Sidecar makes user_id/book_id/page filterable KB attributes.
    attrs = json.loads(by_key[sidecar_key]["Body"])["metadataAttributes"]
    assert attrs["user_id"]["value"]["stringValue"] == "u1"
    assert attrs["book_id"]["value"]["stringValue"] == "book1"
    assert attrs["page"]["value"]["numberValue"] == 1
