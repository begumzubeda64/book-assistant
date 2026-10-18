"""Tests for BookDiscoveryService composition (fallback + cache)."""

from __future__ import annotations

import pytest
from src.integrations.book_providers.base import ProviderError
from src.schemas.books import BookMetadata
from src.services.book_discovery import BookDiscoveryService


def _book(book_id: str, title: str = "T") -> BookMetadata:
    provider = book_id.split(":", 1)[0]
    return BookMetadata(book_id=book_id, provider=provider, title=title)


class FakeProvider:
    def __init__(self, name: str, *, results=None, error=False, by_id=None) -> None:
        self.name = name
        self._results = results or []
        self._error = error
        self._by_id = by_id
        self.search_calls = 0

    async def search(self, query: str, *, limit: int):
        self.search_calls += 1
        if self._error:
            raise ProviderError("boom")
        return list(self._results)

    async def get_by_id(self, source_id: str):
        if self._error:
            raise ProviderError("boom")
        return self._by_id


class DictCache:
    def __init__(self) -> None:
        self.store: dict[str, BookMetadata] = {}

    async def get(self, book_id: str):
        return self.store.get(book_id)

    async def put(self, book: BookMetadata) -> None:
        self.store[book.book_id] = book


@pytest.mark.asyncio
async def test_search_uses_primary_when_it_has_results() -> None:
    primary = FakeProvider("google_books", results=[_book("google_books:1")])
    fallback = FakeProvider("open_library", results=[_book("open_library:x")])
    service = BookDiscoveryService(
        primary=primary, fallback=fallback, cache=DictCache()
    )

    results = await service.search("q")

    assert [b.book_id for b in results] == ["google_books:1"]
    assert fallback.search_calls == 0


@pytest.mark.asyncio
async def test_search_falls_back_when_primary_empty() -> None:
    primary = FakeProvider("google_books", results=[])
    fallback = FakeProvider("open_library", results=[_book("open_library:x")])
    service = BookDiscoveryService(
        primary=primary, fallback=fallback, cache=DictCache()
    )

    results = await service.search("q")

    assert [b.book_id for b in results] == ["open_library:x"]
    assert fallback.search_calls == 1


@pytest.mark.asyncio
async def test_search_falls_back_when_primary_errors() -> None:
    primary = FakeProvider("google_books", error=True)
    fallback = FakeProvider("open_library", results=[_book("open_library:x")])
    service = BookDiscoveryService(
        primary=primary, fallback=fallback, cache=DictCache()
    )

    results = await service.search("q")
    assert [b.book_id for b in results] == ["open_library:x"]


@pytest.mark.asyncio
async def test_search_warms_cache() -> None:
    cache = DictCache()
    primary = FakeProvider("google_books", results=[_book("google_books:1")])
    fallback = FakeProvider("open_library")
    service = BookDiscoveryService(primary=primary, fallback=fallback, cache=cache)

    await service.search("q")
    assert "google_books:1" in cache.store


@pytest.mark.asyncio
async def test_get_book_returns_cached_without_calling_provider() -> None:
    cache = DictCache()
    cache.store["google_books:1"] = _book("google_books:1", "Cached")
    primary = FakeProvider("google_books", by_id=_book("google_books:1", "Fresh"))
    fallback = FakeProvider("open_library")
    service = BookDiscoveryService(primary=primary, fallback=fallback, cache=cache)

    book = await service.get_book("google_books:1")
    assert book is not None
    assert book.title == "Cached"


@pytest.mark.asyncio
async def test_get_book_routes_to_correct_provider() -> None:
    cache = DictCache()
    primary = FakeProvider("google_books", by_id=_book("google_books:1", "G"))
    fallback = FakeProvider("open_library", by_id=_book("open_library:x", "O"))
    service = BookDiscoveryService(primary=primary, fallback=fallback, cache=cache)

    book = await service.get_book("open_library:x")
    assert book is not None
    assert book.title == "O"


@pytest.mark.asyncio
async def test_get_book_unknown_provider_returns_none() -> None:
    service = BookDiscoveryService(
        primary=FakeProvider("google_books"),
        fallback=FakeProvider("open_library"),
        cache=DictCache(),
    )
    assert await service.get_book("bogus:123") is None
    assert await service.get_book("google_books:") is None
