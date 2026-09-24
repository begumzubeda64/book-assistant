"""Book discovery service.

Composes the book providers (primary + fallback) and the optional metadata
cache. Search tries the primary provider first and falls back to the secondary
when the primary yields nothing or errors. Single-book lookups check the cache
first, then the matching provider by the `<provider>:<source_id>` book id.
"""

from __future__ import annotations

from src.core.logging import get_logger
from src.integrations.book_providers.base import BookProvider, ProviderError
from src.repositories.book_cache import BookCacheRepository
from src.schemas.books import BookMetadata

logger = get_logger(__name__)


class BookDiscoveryService:
    def __init__(
        self,
        *,
        primary: BookProvider,
        fallback: BookProvider,
        cache: BookCacheRepository,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._cache = cache
        self._providers = {primary.name: primary, fallback.name: fallback}

    async def search(self, query: str, *, limit: int = 20) -> list[BookMetadata]:
        """Search books, primary provider first, fallback on empty/error."""
        results: list[BookMetadata] = []
        try:
            results = await self._primary.search(query, limit=limit)
        except ProviderError:
            results = []

        if not results:
            try:
                results = await self._fallback.search(query, limit=limit)
            except ProviderError:
                results = []

        # Best-effort cache warm; never blocks or fails the response.
        for book in results:
            await self._cache.put(book)
        return results

    async def get_book(self, book_id: str) -> BookMetadata | None:
        """Fetch a single book by its normalized '<provider>:<source_id>' id."""
        cached = await self._cache.get(book_id)
        if cached is not None:
            return cached

        provider_name, _, source_id = book_id.partition(":")
        provider = self._providers.get(provider_name)
        if provider is None or not source_id:
            return None

        try:
            book = await provider.get_by_id(source_id)
        except ProviderError:
            return None

        if book is not None:
            await self._cache.put(book)
        return book
