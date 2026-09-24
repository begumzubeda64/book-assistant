"""Google Books provider (primary).

Maps the Google Books `volumes` API into the normalized `BookMetadata` shape.
Only public metadata and legitimate discovery/buy links are used; the underlying
book is never fetched or ingested (requirement 2.4).
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

_BASE_URL = "https://www.googleapis.com/books/v1/volumes"
PROVIDER_NAME = "google_books"


class GoogleBooksProvider:
    """Book metadata from the Google Books API."""

    name = PROVIDER_NAME

    def __init__(
        self, client: httpx.AsyncClient, *, api_key: str | None = None
    ) -> None:
        self._client = client
        self._api_key = api_key

    async def search(self, query: str, *, limit: int) -> list[BookMetadata]:
        params: dict[str, Any] = {"q": query, "maxResults": min(max(limit, 1), 40)}
        if self._api_key:
            params["key"] = self._api_key
        data = await self._get(_BASE_URL, params)
        items = data.get("items") or []
        return [self._normalize(item) for item in items]

    async def get_by_id(self, source_id: str) -> BookMetadata | None:
        params: dict[str, Any] = {}
        if self._api_key:
            params["key"] = self._api_key
        try:
            data = await self._get(f"{_BASE_URL}/{source_id}", params)
        except ProviderError:
            raise
        if not data or "volumeInfo" not in data:
            return None
        return self._normalize(data)

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload
        except httpx.HTTPError as exc:
            logger.info(
                "google_books_request_failed",
                extra={"error_type": type(exc).__name__},
            )
            raise ProviderError("Google Books request failed") from exc

    def _normalize(self, item: dict[str, Any]) -> BookMetadata:
        source_id = item.get("id", "")
        info = item.get("volumeInfo", {})
        sale = item.get("saleInfo", {})

        identifiers = self._identifiers(info, source_id)
        page_count = info.get("pageCount")
        estimate = ReadingEstimate(
            page_count=page_count,
            minutes=estimate_reading_minutes(
                word_count=None, page_count=page_count
            ),
        )

        return BookMetadata(
            book_id=f"{PROVIDER_NAME}:{source_id}",
            provider=PROVIDER_NAME,
            title=info.get("title", "Untitled"),
            authors=info.get("authors", []) or [],
            description=info.get("description"),
            categories=info.get("categories", []) or [],
            cover_url=self._cover(info),
            published_date=info.get("publishedDate"),
            language=info.get("language"),
            identifiers=identifiers,
            links=self._links(info, sale),
            reading_estimate=estimate,
        )

    @staticmethod
    def _identifiers(info: dict[str, Any], source_id: str) -> BookIdentifiers:
        isbn_10: str | None = None
        isbn_13: str | None = None
        for entry in info.get("industryIdentifiers", []) or []:
            if entry.get("type") == "ISBN_10":
                isbn_10 = entry.get("identifier")
            elif entry.get("type") == "ISBN_13":
                isbn_13 = entry.get("identifier")
        return BookIdentifiers(
            isbn_10=isbn_10, isbn_13=isbn_13, source_id=source_id
        )

    @staticmethod
    def _cover(info: dict[str, Any]) -> str | None:
        images = info.get("imageLinks") or {}
        return images.get("thumbnail") or images.get("smallThumbnail")

    @staticmethod
    def _links(info: dict[str, Any], sale: dict[str, Any]) -> list[ExternalLink]:
        links: list[ExternalLink] = []
        if info.get("infoLink"):
            links.append(
                ExternalLink(kind="info", label="More info", url=info["infoLink"])
            )
        if info.get("previewLink"):
            links.append(
                ExternalLink(
                    kind="preview", label="Preview", url=info["previewLink"]
                )
            )
        if sale.get("buyLink"):
            links.append(
                ExternalLink(kind="buy", label="Buy", url=sale["buyLink"])
            )
        return links
