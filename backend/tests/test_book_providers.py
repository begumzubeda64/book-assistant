"""Tests for the book provider adapters and metadata normalization."""

from __future__ import annotations

import httpx
import pytest
from src.integrations.book_providers.base import (
    ProviderError,
    estimate_reading_minutes,
)
from src.integrations.book_providers.google_books import GoogleBooksProvider
from src.integrations.book_providers.open_library import OpenLibraryProvider

GOOGLE_VOLUME = {
    "id": "vol123",
    "volumeInfo": {
        "title": "Dune",
        "authors": ["Frank Herbert"],
        "description": "A desert planet epic.",
        "categories": ["Fiction"],
        "pageCount": 412,
        "publishedDate": "1965",
        "language": "en",
        "imageLinks": {"thumbnail": "http://img/thumb.jpg"},
        "infoLink": "http://books/info",
        "previewLink": "http://books/preview",
        "industryIdentifiers": [
            {"type": "ISBN_10", "identifier": "0441172717"},
            {"type": "ISBN_13", "identifier": "9780441172719"},
        ],
    },
    "saleInfo": {"buyLink": "http://books/buy"},
}

OPEN_LIBRARY_DOC = {
    "key": "/works/OL45804W",
    "title": "Fantastic Mr Fox",
    "author_name": ["Roald Dahl"],
    "first_publish_year": 1970,
    "isbn": ["0140328726", "9780140328721"],
    "cover_i": 8739161,
    "language": ["eng"],
    "number_of_pages_median": 96,
    "subject": ["Foxes", "Children"],
}


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


def test_estimate_reading_minutes() -> None:
    assert estimate_reading_minutes(word_count=2000, page_count=None) == 10
    # From pages: 100 * 275 / 200 = 137.5 -> 138
    assert estimate_reading_minutes(word_count=None, page_count=100) == 138
    assert estimate_reading_minutes(word_count=None, page_count=None) is None
    assert estimate_reading_minutes(word_count=0, page_count=None) is None


@pytest.mark.asyncio
async def test_google_books_search_normalizes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "volumes" in str(request.url)
        return httpx.Response(200, json={"items": [GOOGLE_VOLUME]})

    async with _client(handler) as client:
        provider = GoogleBooksProvider(client)
        results = await provider.search("dune", limit=5)

    assert len(results) == 1
    book = results[0]
    assert book.book_id == "google_books:vol123"
    assert book.provider == "google_books"
    assert book.title == "Dune"
    assert book.authors == ["Frank Herbert"]
    assert book.identifiers.isbn_13 == "9780441172719"
    assert book.reading_estimate.page_count == 412
    assert book.reading_estimate.minutes is not None
    kinds = {link.kind for link in book.links}
    assert {"info", "preview", "buy"} <= kinds


@pytest.mark.asyncio
async def test_google_books_get_by_id_missing_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with _client(handler) as client:
        provider = GoogleBooksProvider(client)
        assert await provider.get_by_id("nope") is None


@pytest.mark.asyncio
async def test_google_books_http_error_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    async with _client(handler) as client:
        provider = GoogleBooksProvider(client)
        with pytest.raises(ProviderError):
            await provider.search("dune", limit=5)


@pytest.mark.asyncio
async def test_open_library_search_normalizes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"docs": [OPEN_LIBRARY_DOC]})

    async with _client(handler) as client:
        provider = OpenLibraryProvider(client)
        results = await provider.search("fox", limit=5)

    assert len(results) == 1
    book = results[0]
    assert book.book_id == "open_library:OL45804W"
    assert book.title == "Fantastic Mr Fox"
    assert book.authors == ["Roald Dahl"]
    assert book.identifiers.isbn_13 == "9780140328721"
    assert book.identifiers.isbn_10 == "0140328726"
    assert book.published_date == "1970"
    assert book.cover_url is not None
    assert any(link.kind == "borrow" for link in book.links)
