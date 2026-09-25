"""MCP tool server.

Exposes a small, explicitly allowlisted set of tools to the agents over the
Model Context Protocol. This is the isolated tool tier: agents call these tools
instead of touching AWS directly, and a misbehaving tool is contained here
(decisions.md, security.md).

Allowlisted tools (MVP, ingestion):
- get_authorized_content : fetch an authorized user's uploaded PDF bytes
- ingest_to_knowledge_base : ingest prepared chunks into the KB (GraphRAG)

More tools (GraphRAG retrieval, concept persistence) are added with the
discussion/reading groups.
"""

from __future__ import annotations

import base64
from typing import Any

from src.agents.shared.ports import (
    BookContentPort,
    GraphRAGRetrievalPort,
    ReadingStorePort,
    TextGenerationPort,
)
from src.agents.shared.types import PreparedChunk
from src.core.config import Settings
from src.mcp_server.tools.content import ContentTool
from src.mcp_server.tools.knowledge_base import KnowledgeBaseTool

# The single source of truth for what the agents are permitted to invoke.
TOOL_ALLOWLIST = frozenset(
    {
        "get_authorized_content",
        "ingest_to_knowledge_base",
        "get_book_content",
        "generate_text",
        "store_reading_result",
        "graphrag_retrieve",
    }
)


def build_tools_from_settings(
    settings: Settings,
) -> tuple[ContentTool, KnowledgeBaseTool]:
    """Construct the real tool adapters from configuration."""
    import boto3

    s3 = boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
    )
    bedrock_agent = boto3.client(
        "bedrock-agent", region_name=settings.aws_region
    )

    if not settings.uploads_bucket_name:
        raise RuntimeError("uploads_bucket_name is required for the MCP server")
    if not (
        settings.kb_chunk_bucket_name
        and settings.knowledge_base_id
        and settings.knowledge_base_data_source_id
    ):
        raise RuntimeError("Knowledge Base configuration is incomplete")

    content = ContentTool(s3, settings.uploads_bucket_name)
    kb = KnowledgeBaseTool(
        s3_client=s3,
        bedrock_agent_client=bedrock_agent,
        chunk_bucket=settings.kb_chunk_bucket_name,
        knowledge_base_id=settings.knowledge_base_id,
        data_source_id=settings.knowledge_base_data_source_id,
    )
    return content, kb


def create_mcp_server(content: ContentTool, kb: KnowledgeBaseTool) -> Any:
    """Create the FastMCP server with the allowlisted tools registered."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("book-companion-tools")

    @server.tool(name="get_authorized_content")
    def get_authorized_content(user_id: str, object_key: str) -> str:
        """Return base64-encoded PDF bytes for an authorized object."""
        raw = content.fetch_pdf_bytes(user_id, object_key)
        return base64.b64encode(raw).decode("ascii")

    @server.tool(name="ingest_to_knowledge_base")
    def ingest_to_knowledge_base(
        user_id: str, book_id: str, chunks: list[dict[str, Any]]
    ) -> str:
        """Ingest prepared chunks into the Knowledge Base; returns a ref."""
        prepared = [PreparedChunk.model_validate(c) for c in chunks]
        return kb.ingest_chunks(
            user_id=user_id, book_id=book_id, chunks=prepared
        )

    return server


def register_reading_tools(
    server: Any,
    *,
    book_content: BookContentPort,
    generator: TextGenerationPort,
    reading_store: ReadingStorePort,
) -> None:
    """Register the adaptive-reading tools on an existing MCP server."""

    @server.tool(name="get_book_content")
    def get_book_content(
        user_id: str, book_id: str, chapter_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return prepared chunks for an authorized book/chapter."""
        chunks = book_content.get_chunks(
            user_id=user_id, book_id=book_id, chapter_id=chapter_id
        )
        return [c.model_dump() for c in chunks]

    @server.tool(name="generate_text")
    def generate_text(prompt: str, max_words: int) -> str:
        """Generate text for the prompt (foundation model)."""
        return generator.generate(prompt=prompt, max_words=max_words)

    @server.tool(name="store_reading_result")
    def store_reading_result(user_id: str, reading_id: str, payload: str) -> str:
        """Store a generated adaptive-reading result; returns its location."""
        return reading_store.store_reading(
            user_id=user_id, reading_id=reading_id, payload=payload
        )


def register_discussion_tools(
    server: Any, *, retriever: GraphRAGRetrievalPort
) -> None:
    """Register the GraphRAG discussion tools on an existing MCP server."""

    @server.tool(name="graphrag_retrieve")
    def graphrag_retrieve(
        user_id: str, book_id: str, query: str, top_k: int = 8
    ) -> list[dict[str, Any]]:
        """Retrieve passages relevant to the query (user-scoped)."""
        passages = retriever.retrieve(
            user_id=user_id, book_id=book_id, query=query, top_k=top_k
        )
        return [p.model_dump() for p in passages]
