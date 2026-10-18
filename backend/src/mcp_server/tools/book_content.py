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
        # Chunks are stored as `<chunk>.txt` (document text) with a companion
        # `<chunk>.txt.metadata.json` (filterable KB metadata). Read the text
        # objects and reconstruct provenance from their sidecars.
        prefix = chunk_prefix(user_id, book_id)
        chunks: list[PreparedChunk] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                if not key.endswith(".txt"):
                    continue  # skip sidecars and anything else
                text = (
                    self._s3.get_object(Bucket=self._bucket, Key=key)["Body"]
                    .read()
                    .decode("utf-8")
                )
                source = self._read_source(f"{key}.metadata.json", book_id)
                if chapter_id and source.chapter_id != chapter_id:
                    continue
                chunks.append(
                    PreparedChunk(
                        chunk_id=key.rsplit("/", 1)[-1].removesuffix(".txt"),
                        text=text,
                        word_count=len(text.split()),
                        source=source,
                    )
                )
        chunks.sort(key=lambda c: (c.source.page or 0, c.chunk_id))
        return chunks

    def _read_source(self, sidecar_key: str, book_id: str) -> SourceRef:
        try:
            raw = self._s3.get_object(Bucket=self._bucket, Key=sidecar_key)
            attrs = json.loads(raw["Body"].read()).get("metadataAttributes", {})
        except Exception:
            return SourceRef(book_id=book_id)

        def val(name: str) -> Any:
            v = attrs.get(name, {}).get("value", {})
            return v.get("stringValue") or v.get("numberValue")

        page = val("page")
        return SourceRef(
            book_id=val("book_id") or book_id,
            chapter_title=val("chapter_title"),
            section=val("section"),
            page=int(page) if page is not None else None,
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
