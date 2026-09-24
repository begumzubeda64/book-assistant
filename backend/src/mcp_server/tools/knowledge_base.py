"""Knowledge-base ingestion tool (MCP).

Ingests prepared chunks into a Bedrock Knowledge Base backed by Neptune
Analytics (GraphRAG). Each chunk is written to S3 under a per-user, per-book
prefix with its source metadata preserved, then a Knowledge Base ingestion job
is started so the managed pipeline builds the graph.

The chunk store prefix encodes the owning ``user_id`` so retrieval can later be
scoped to content the user may access (security.md). This adapter has the real
boto3 shape; tests exercise it via a fake implementing the same port.
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.shared.types import PreparedChunk
from src.core.logging import get_logger

logger = get_logger(__name__)


def chunk_prefix(user_id: str, book_id: str) -> str:
    """Private, ownership-scoped prefix for a book's prepared chunks."""
    return f"prepared/{user_id}/{book_id}/"


class KnowledgeBaseTool:
    """Bedrock Knowledge Base ingestion (Neptune Analytics GraphRAG)."""

    def __init__(
        self,
        *,
        s3_client: Any,
        bedrock_agent_client: Any,
        chunk_bucket: str,
        knowledge_base_id: str,
        data_source_id: str,
    ) -> None:
        self._s3 = s3_client
        self._bedrock = bedrock_agent_client
        self._bucket = chunk_bucket
        self._kb_id = knowledge_base_id
        self._data_source_id = data_source_id

    def ingest_chunks(
        self,
        *,
        user_id: str,
        book_id: str,
        chunks: list[PreparedChunk],
    ) -> str:
        prefix = chunk_prefix(user_id, book_id)
        for chunk in chunks:
            self._s3.put_object(
                Bucket=self._bucket,
                Key=f"{prefix}{chunk.chunk_id}.json",
                Body=self._serialize(chunk, user_id),
                ContentType="application/json",
            )
        response = self._bedrock.start_ingestion_job(
            knowledgeBaseId=self._kb_id,
            dataSourceId=self._data_source_id,
        )
        ingestion_ref = str(
            response.get("ingestionJob", {}).get("ingestionJobId", "")
        )
        logger.info(
            "kb_ingestion_started",
            extra={"book_id": book_id, "chunk_count": len(chunks)},
        )
        return ingestion_ref

    @staticmethod
    def _serialize(chunk: PreparedChunk, user_id: str) -> bytes:
        # Preserve provenance and the ownership boundary alongside the text.
        payload = {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "metadata": {
                "user_id": user_id,
                **chunk.source.model_dump(exclude_none=True),
            },
        }
        return json.dumps(payload).encode("utf-8")
