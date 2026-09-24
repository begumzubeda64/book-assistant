"""Deterministic ingestion nodes.

These are plain algorithms (no model): fetch the PDF via the content tool,
extract text per page with pypdf, chunk while preserving chapter/section/page/
source metadata, and ingest via the knowledge-base tool. Each node is a small
pure-ish function so it can be unit-tested directly.
"""

from __future__ import annotations

import io
import re

from src.agents.shared.ports import ContentStorePort, KnowledgeBasePort
from src.agents.shared.types import PreparedChunk, SourceRef

# Target words per chunk. Small enough for retrieval granularity, large enough
# to preserve local context.
CHUNK_TARGET_WORDS = 220

# Heading heuristic for chapter detection (e.g. "Chapter 3", "CHAPTER IV").
_CHAPTER_RE = re.compile(r"^\s*(chapter|part)\s+([\dIVXLC]+)\b", re.IGNORECASE)


def extract_pages(pdf_bytes: bytes) -> list[str]:
    """Extract text per page using pypdf. Returns one string per page."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def _detect_chapter(text: str) -> str | None:
    """Return a chapter label if the text begins with a chapter heading."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _CHAPTER_RE.match(stripped)
        return stripped if match else None
    return None


def _split_words(text: str, target: int) -> list[str]:
    """Split text into ~target-word segments on whitespace."""
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[i : i + target]) for i in range(0, len(words), target)
    ]


def chunk_pages(
    book_id: str, pages: list[str], *, target_words: int = CHUNK_TARGET_WORDS
) -> list[PreparedChunk]:
    """Chunk pages into prepared chunks, preserving page/chapter provenance."""
    chunks: list[PreparedChunk] = []
    current_chapter: str | None = None

    for page_index, page_text in enumerate(pages, start=1):
        if not page_text.strip():
            continue
        detected = _detect_chapter(page_text)
        if detected:
            current_chapter = detected

        for segment_index, segment in enumerate(
            _split_words(page_text, target_words)
        ):
            chunk_id = f"{book_id}:p{page_index}:s{segment_index}"
            chunks.append(
                PreparedChunk(
                    chunk_id=chunk_id,
                    text=segment,
                    word_count=len(segment.split()),
                    source=SourceRef(
                        book_id=book_id,
                        chapter_title=current_chapter,
                        page=page_index,
                    ),
                )
            )
    return chunks


def fetch_pdf(content: ContentStorePort, user_id: str, object_key: str) -> bytes:
    """Fetch the authorized PDF bytes via the content tool."""
    return content.fetch_pdf_bytes(user_id, object_key)


def ingest_chunks(
    kb: KnowledgeBasePort,
    *,
    user_id: str,
    book_id: str,
    chunks: list[PreparedChunk],
) -> str:
    """Ingest prepared chunks into the knowledge base via the KB tool."""
    return kb.ingest_chunks(user_id=user_id, book_id=book_id, chunks=chunks)
