"""Ingestion graph state."""

from __future__ import annotations

from typing import TypedDict

from src.agents.shared.types import PreparedChunk


class IngestionState(TypedDict, total=False):
    """State threaded through the ingestion graph.

    Inputs: job_id, user_id, book_id, object_key.
    Populated by nodes: pdf_bytes, pages, chunks, ingestion_ref, error.
    """

    job_id: str
    user_id: str
    book_id: str
    object_key: str

    pdf_bytes: bytes
    pages: list[str]
    chunks: list[PreparedChunk]
    ingestion_ref: str
    error: str
