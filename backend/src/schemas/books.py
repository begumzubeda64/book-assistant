"""Book discovery schemas.

Normalized, provider-agnostic book metadata returned by the discovery API. The
same `BookMetadata` shape is produced whether the source is Google Books or Open
Library, so callers never depend on a provider's payload format.
"""

from __future__ import annotations

from pydantic import Field

from src.schemas.base import APIModel, Page


class BookIdentifiers(APIModel):
    """External identifiers for a book."""

    isbn_10: str | None = None
    isbn_13: str | None = None
    # Provider-native id (e.g. Google Books volume id or Open Library work key).
    source_id: str | None = None


class ExternalLink(APIModel):
    """A legitimate discovery / buy / borrow link.

    These are display-only discovery links. They are never treated as
    authorization to ingest the underlying book (requirement 2.4, security
    steering).
    """

    kind: str = Field(..., description="e.g. 'info', 'buy', 'borrow', 'preview'")
    label: str
    url: str


class ReadingEstimate(APIModel):
    """Estimated original reading time, when derivable."""

    word_count: int | None = None
    page_count: int | None = None
    minutes: int | None = Field(
        default=None, description="Estimated minutes at the default WPM"
    )


class BookMetadata(APIModel):
    """Normalized metadata for a single book."""

    book_id: str = Field(..., description="Stable id: '<provider>:<source_id>'")
    provider: str = Field(..., description="Source provider, e.g. 'google_books'")
    title: str
    authors: list[str] = Field(default_factory=list)
    description: str | None = None
    categories: list[str] = Field(default_factory=list)
    cover_url: str | None = None
    published_date: str | None = None
    language: str | None = None
    identifiers: BookIdentifiers = Field(default_factory=BookIdentifiers)
    links: list[ExternalLink] = Field(default_factory=list)
    reading_estimate: ReadingEstimate = Field(default_factory=ReadingEstimate)


class BookSearchResults(Page[BookMetadata]):
    """Paginated search results."""

    query: str
