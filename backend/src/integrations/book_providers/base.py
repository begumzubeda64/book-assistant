"""Common book-provider interface and shared helpers.

Providers (Google Books, Open Library) implement `BookProvider`, returning the
normalized `BookMetadata` shape so the service and callers stay provider-
agnostic. Estimation of the original reading time is centralized here.
"""

from __future__ import annotations

from typing import Protocol

from src.schemas.books import BookMetadata

# Default reading speed for the ORIGINAL reading-time estimate shown in
# discovery. This is distinct from the adaptive-reading word budget (defined in
# the reading pipeline); it is only used to estimate how long the full book
# would take to read.
DEFAULT_WORDS_PER_MINUTE = 200
# Rough words-per-page heuristic used when only a page count is available.
WORDS_PER_PAGE = 275


def estimate_reading_minutes(
    *, word_count: int | None, page_count: int | None
) -> int | None:
    """Estimate original reading time in minutes.

    Prefers a real word count; otherwise approximates from page count. Returns
    None when neither is available (requirement 4.1 shows the estimate only when
    sufficient information exists).
    """
    words = word_count
    if words is None and page_count is not None:
        words = page_count * WORDS_PER_PAGE
    if not words or words <= 0:
        return None
    return max(1, round(words / DEFAULT_WORDS_PER_MINUTE))


class ProviderError(Exception):
    """Raised when a provider call fails (network, parsing, upstream error)."""


class BookProvider(Protocol):
    """A book metadata provider."""

    name: str

    async def search(self, query: str, *, limit: int) -> list[BookMetadata]:
        """Search books by free-text query (title, author, or ISBN)."""
        ...

    async def get_by_id(self, source_id: str) -> BookMetadata | None:
        """Fetch a single book by the provider-native id."""
        ...
