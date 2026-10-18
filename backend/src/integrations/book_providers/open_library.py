"""Open Library provider (fallback).

Maps the Open Library search/works APIs into the normalized `BookMetadata`
shape. Used when the primary provider returns nothing or fails.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.core.logging import get_logger
from src.integrations.book_providers.base import (
    ProviderError,
    estimate_reading_minutes,
)
from src.schemas.books import (
    BookIdentifiers,
    BookMetadata,
    ExternalLink,
    ReadingEstimate,
)

logger = get_logger(__name__)

_SEARCH_URL = "https://openlibrary.org/search.json"
_BASE = "https://openlibrary.org"
PROVIDER_NAME = "open_library"

# Only request the fields we normalize, to keep responses small.
_SEARCH_FIELDS = ",".join(
    [
        "key",
        "title",
        "author_name",
        "first_publish_year",
        "isbn",
        "cover_i",
        "language",
        "number_of_pages_median",
        "subject",
    ]
)


class OpenLibraryProvider:
    """Book metadata from Open Library."""

    name = PROVIDER_NAME

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, *, limit: int) -> list[BookMetadata]:
        params = {"q": query, "limit": min(max(limit, 1), 40), "fields": _SEARCH_FIELDS}
        data = await self._get(_SEARCH_URL, params)
        docs = data.get("docs") or []
        return [self._normalize(doc) for doc in docs]

    async def get_by_id(self, source_id: str) -> BookMetadata | None:
        # source_id is an Open Library work key, e.g. "OL45804W".
        params = {"q": f"key:/works/{source_id}", "fields": _SEARCH_FIELDS}
        data = await self._get(_SEARCH_URL, params)
        docs = data.get("docs") or []
        if not docs:
            return None
        return self._normalize(docs[0])

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload
        except httpx.HTTPError as exc:
            logger.info(
                "open_library_request_failed",
                extra={"error_type": type(exc).__name__},
            )
            raise ProviderError("Open Library request failed") from exc

    def _normalize(self, doc: dict[str, Any]) -> BookMetadata:
        work_key = str(doc.get("key", "")).removeprefix("/works/")
        pages = doc.get("number_of_pages_median")
        isbns = doc.get("isbn") or []
        isbn_13 = next((i for i in isbns if len(i) == 13), None)
        isbn_10 = next((i for i in isbns if len(i) == 10), None)
        languages = doc.get("language") or []

        links = [
            ExternalLink(
                kind="borrow",
                label="Open Library",
                url=f"{_BASE}/works/{work_key}",
            )
        ]

        return BookMetadata(
            book_id=f"{PROVIDER_NAME}:{work_key}",
            provider=PROVIDER_NAME,
            title=doc.get("title", "Untitled"),
            authors=doc.get("author_name", []) or [],
            description=None,
            categories=(doc.get("subject", []) or [])[:8],
            cover_url=self._cover(doc.get("cover_i")),
            published_date=(
                str(doc["first_publish_year"])
                if doc.get("first_publish_year")
                else None
            ),
            language=languages[0] if languages else None,
            identifiers=BookIdentifiers(
                isbn_10=isbn_10, isbn_13=isbn_13, source_id=work_key
            ),
            links=links,
            reading_estimate=ReadingEstimate(
                page_count=pages,
                minutes=estimate_reading_minutes(
                    word_count=None, page_count=pages
                ),
            ),
        )

    @staticmethod
    def _cover(cover_id: int | None) -> str | None:
        if not cover_id:
            return None
        return f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
