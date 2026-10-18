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
            # The document body is the chunk TEXT (what gets embedded + graphed),
            # not a JSON wrapper. A companion ``<key>.metadata.json`` makes
            # user_id/book_id/provenance FILTERABLE KB attributes so retrieval
            # can be scoped to the owner (security.md) and cite sources.
            key = f"{prefix}{chunk.chunk_id}.txt"
            self._s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=chunk.text.encode("utf-8"),
                ContentType="text/plain",
            )
            self._s3.put_object(
                Bucket=self._bucket,
                Key=f"{key}.metadata.json",
                Body=self._metadata_sidecar(chunk, user_id),
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

    def delete_book(self, *, user_id: str, book_id: str) -> int:
        """Remove a book's prepared chunks from the KB, scoped to the user.

        Deletes every chunk object under the user's per-book prefix, then
        re-triggers an ingestion sync so the managed pipeline reconciles the
        removed source documents out of the Neptune graph. Returns the number of
        chunk objects deleted.
        """
        prefix = chunk_prefix(user_id, book_id)
        paginator = self._s3.get_paginator("list_objects_v2")
        to_delete: list[dict[str, str]] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                to_delete.append({"Key": obj["Key"]})

        deleted = 0
        # delete_objects takes up to 1000 keys per call.
        for i in range(0, len(to_delete), 1000):
            batch = to_delete[i : i + 1000]
            if not batch:
                continue
            self._s3.delete_objects(
                Bucket=self._bucket, Delete={"Objects": batch}
            )
            deleted += len(batch)

        if deleted:
            # Re-sync so the graph drops the removed documents.
            self._bedrock.start_ingestion_job(
                knowledgeBaseId=self._kb_id, dataSourceId=self._data_source_id
            )
        logger.info(
            "kb_book_deleted",
            extra={"book_id": book_id, "deleted_chunk_objects": deleted},
        )
        return deleted

    @staticmethod
    def _metadata_sidecar(chunk: PreparedChunk, user_id: str) -> bytes:
        """Bedrock KB metadata sidecar: makes these attributes FILTERABLE.

        Format: {"metadataAttributes": {"<key>": {"value": {"type": ..,
        "stringValue"/"numberValue": ..}, "includeForEmbedding": false}}}.
        Ownership (user_id, book_id) and provenance (chunk_id, chapter, page)
        are preserved so retrieval can be user/book-scoped and cite sources.
        """
        src = chunk.source

        def attr(value: object) -> dict[str, Any]:
            if isinstance(value, bool):
                return {"value": {"type": "BOOLEAN", "booleanValue": value}}
            if isinstance(value, int):
                return {"value": {"type": "NUMBER", "numberValue": value}}
            return {"value": {"type": "STRING", "stringValue": str(value)}}

        attributes: dict[str, Any] = {
            "user_id": attr(user_id),
            "book_id": attr(src.book_id),
            "chunk_id": attr(chunk.chunk_id),
        }
        if src.chapter_title:
            attributes["chapter_title"] = attr(src.chapter_title)
        if src.section:
            attributes["section"] = attr(src.section)
        if src.page is not None:
            attributes["page"] = attr(src.page)

        return json.dumps({"metadataAttributes": attributes}).encode("utf-8")
