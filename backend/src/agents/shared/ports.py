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


class BookContentPort(Protocol):
    """Read access to a user's prepared (ingested) book content."""

    def get_chunks(
        self, *, user_id: str, book_id: str, chapter_id: str | None = None
    ) -> list[PreparedChunk]:
        """Return prepared chunks for a book/chapter the user may access."""
        ...


class TextGenerationPort(Protocol):
    """Foundation-model text generation (the only model call in a graph)."""

    def generate(self, *, prompt: str, max_words: int) -> str:
        """Generate text for the prompt, targeting an approximate word budget."""
        ...


class ReadingStorePort(Protocol):
    """Persistence for generated adaptive-reading results (backed by S3)."""

    def store_reading(self, *, user_id: str, reading_id: str, payload: str) -> str:
        """Store a reading result. Returns its storage location."""
        ...
