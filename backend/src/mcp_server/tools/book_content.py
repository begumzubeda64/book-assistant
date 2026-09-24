"""Book-content and reading-result tools (MCP).

`BookContentTool` reads a user's prepared chunks back from the chunk store
(written during ingestion), scoped to the owning user's prefix.
`ReadingStoreTool` persists generated adaptive-reading results.

Both re-enforce the per-user ownership boundary via key prefixes (security.md).
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.shared.types import PreparedChunk, SourceRef
from src.mcp_server.tools.knowledge_base import chunk_prefix


class BookContentTool:
    """Read prepared chunks for an authorized user's book."""

    def __init__(self, s3_client: Any, chunk_bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = chunk_bucket

    def get_chunks(
        self, *, user_id: str, book_id: str, chapter_id: str | None = None
    ) -> list[PreparedChunk]:
        prefix = chunk_prefix(user_id, book_id)
        chunks: list[PreparedChunk] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                body = self._s3.get_object(Bucket=self._bucket, Key=obj["Key"])
                payload = json.loads(body["Body"].read())
                chunk = self._to_chunk(payload)
                if chapter_id and chunk.source.chapter_id != chapter_id:
                    continue
                chunks.append(chunk)
        chunks.sort(key=lambda c: (c.source.page or 0, c.chunk_id))
        return chunks

    @staticmethod
    def _to_chunk(payload: dict[str, Any]) -> PreparedChunk:
        meta = payload.get("metadata", {})
        text = payload.get("text", "")
        return PreparedChunk(
            chunk_id=payload["chunk_id"],
            text=text,
            word_count=len(text.split()),
            source=SourceRef(
                book_id=meta.get("book_id", ""),
                chapter_id=meta.get("chapter_id"),
                chapter_title=meta.get("chapter_title"),
                section=meta.get("section"),
                page=meta.get("page"),
            ),
        )


class ReadingStoreTool:
    """Persist generated adaptive-reading results to S3."""

    def __init__(self, s3_client: Any, results_bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = results_bucket

    def store_reading(
        self, *, user_id: str, reading_id: str, payload: str
    ) -> str:
        key = f"readings/{user_id}/{reading_id}.json"
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=payload.encode("utf-8"),
            ContentType="application/json",
        )
        return f"s3://{self._bucket}/{key}"
