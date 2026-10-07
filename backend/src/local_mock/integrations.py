"""Local integration fakes for mock mode.

These implement the same ports as the AWS-backed integrations but keep
everything in process memory:

- ``LocalStorage`` — holds uploaded PDF bytes in memory; ``presign_put`` returns
  a local sentinel URL the frontend/backend treat specially (no real S3 PUT).
- ``LocalContentStore`` — returns the in-memory PDF bytes to the ingestion agent.
- ``LocalKnowledgeBase`` — stores prepared chunks in memory and does simple
  keyword retrieval (stands in for Bedrock KB + Neptune GraphRAG).
- ``MockTextGeneration`` — deterministic, clearly-marked output (no model call).
- ``LocalReadingStore`` — keeps reading-result JSON in memory.
"""

from __future__ import annotations

import json
from typing import Any

from src.agents.shared.ports import PreparedChunk, RetrievedPassage
from src.core.errors import ForbiddenError
from src.integrations.s3_storage import owns_key

# A visible marker so mocked AI output is never mistaken for the real thing.
MOCK_NOTE = "[local mock output — not real AI generation]"


class LocalBlobStore:
    """Shared in-memory blob store (uploads + reading results)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes | None:
        return self.objects.get(key)


class LocalStorage:
    """StoragePort: presign returns a sentinel; bytes live in the blob store."""

    def __init__(self, blobs: LocalBlobStore) -> None:
        self._blobs = blobs

    def presign_put(
        self, object_key: str, *, content_type: str, expires_in: int
    ) -> str:
        # Sentinel URL the frontend recognizes to skip a real S3 PUT.
        return f"local-mock://upload/{object_key}"

    def object_exists(self, object_key: str) -> bool:
        return object_key in self._blobs.objects


class LocalContentStore:
    """ContentStorePort: returns in-memory PDF bytes for the ingestion agent."""

    def __init__(self, blobs: LocalBlobStore) -> None:
        self._blobs = blobs

    def fetch_pdf_bytes(self, user_id: str, object_key: str) -> bytes:
        if not owns_key(user_id, object_key):
            raise ForbiddenError("Not authorized to access this object")
        data = self._blobs.get(object_key)
        if data is None:
            # In mock mode the browser upload is simulated; provide placeholder
            # text so ingestion still produces chunks for a demo.
            placeholder = (
                "Chapter 1 Introduction\n"
                "This is placeholder book content used in local mock mode. "
                "It exists so the ingestion, adaptive-reading, and discussion "
                "flows can run end to end without AWS. "
            ) * 40
            return _text_as_pdf(placeholder)
        return data


class LocalKnowledgeBase:
    """KnowledgeBasePort + GraphRAGRetrievalPort over in-memory chunks."""

    def __init__(self) -> None:
        # (user_id, book_id) -> chunks
        self._chunks: dict[tuple[str, str], list[PreparedChunk]] = {}

    def ingest_chunks(
        self, *, user_id: str, book_id: str, chunks: list[PreparedChunk]
    ) -> str:
        self._chunks[(user_id, book_id)] = chunks
        return f"local-kb://{user_id}/{book_id}"

    def get_chunks(
        self, *, user_id: str, book_id: str, chapter_id: str | None = None
    ) -> list[PreparedChunk]:
        return list(self._chunks.get((user_id, book_id), []))

    def retrieve(
        self, *, user_id: str, book_id: str, query: str, top_k: int = 8
    ) -> list[RetrievedPassage]:
        chunks = self._chunks.get((user_id, book_id), [])
        terms = {t for t in query.lower().split() if len(t) > 2}
        scored: list[tuple[int, PreparedChunk]] = []
        for chunk in chunks:
            text = chunk.text.lower()
            score = sum(text.count(t) for t in terms)
            scored.append((score, chunk))
        scored.sort(key=lambda s: s[0], reverse=True)
        top = [c for score, c in scored if score > 0][:top_k] or [
            c for _, c in scored[:top_k]
        ]
        return [
            RetrievedPassage(
                text=c.text,
                chunk_id=c.chunk_id,
                chapter_title=c.source.chapter_title,
                section=c.source.section,
                page=c.source.page,
            )
            for c in top
        ]


class MockTextGeneration:
    """TextGenerationPort: deterministic, clearly-marked output (no model)."""

    def generate(self, *, prompt: str, max_words: int) -> str:
        # Pull the source material out of the prompt and echo a condensed,
        # readable paragraph, clearly marked as a mock.
        source = prompt.split("SOURCE MATERIAL:")[-1]
        words = source.split()
        # Keep roughly a third of the budget so it reads like a condensation.
        kept = " ".join(words[: min(len(words), max(60, max_words // 3))])
        return (
            f"{MOCK_NOTE}\n\n"
            "Here is a condensed, readable take on the selected passages. "
            f"{kept.strip()}"
        )


class LocalReadingStore:
    """ReadingStorePort: keep reading-result JSON in memory."""

    def __init__(self) -> None:
        self.results: dict[str, dict[str, Any]] = {}

    def store_reading(
        self, *, user_id: str, reading_id: str, payload: str
    ) -> str:
        self.results[f"{user_id}/{reading_id}"] = json.loads(payload)
        return f"local-mock://readings/{user_id}/{reading_id}"

    async def get(self, user_id: str, reading_id: str) -> dict[str, Any] | None:
        return self.results.get(f"{user_id}/{reading_id}")


def _text_as_pdf(text: str) -> bytes:
    """Carry plain text behind the ingestion node's local-mock sentinel.

    Avoids a PDF-generation dependency; ``extract_pages`` recognizes the prefix
    and reads the text back directly.
    """
    return b"%PDF-LOCALMOCK%" + text.encode("utf-8")
