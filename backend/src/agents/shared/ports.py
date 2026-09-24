"""Agent-tier ports.

Agents never call AWS or business logic directly; they reach capabilities
through the MCP tool server. These Protocols describe the tool surface the
ingestion graph depends on, so nodes can be tested against fakes and the real
implementations live behind the MCP boundary (decisions.md, security.md).
"""

from __future__ import annotations

from typing import Protocol

from src.agents.shared.types import PreparedChunk


class ContentStorePort(Protocol):
    """Access to an authorized user's uploaded content (backed by S3)."""

    def fetch_pdf_bytes(self, user_id: str, object_key: str) -> bytes:
        """Return the raw PDF bytes for an object the user is authorized to use."""
        ...


class KnowledgeBasePort(Protocol):
    """Ingestion into the Bedrock Knowledge Base / Neptune Analytics graph."""

    def ingest_chunks(
        self,
        *,
        user_id: str,
        book_id: str,
        chunks: list[PreparedChunk],
    ) -> str:
        """Ingest prepared chunks for a book. Returns an ingestion reference.

        Must preserve per-chunk source identifiers and the owning user's access
        boundary so GraphRAG retrieval can be scoped later (security.md).
        """
        ...
