"""Book discovery endpoints.

    GET /api/v1/books/search
    GET /api/v1/books/{book_id}

Returns normalized, provider-agnostic metadata with legitimate discovery links.
The underlying book is never ingested from these links (requirement 2.4).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from src.api.dependencies import BookServiceDep, CurrentUser
from src.core.errors import NotFoundError
from src.schemas.books import BookMetadata, BookSearchResults

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/search", response_model=BookSearchResults)
async def search_books(
    _user: CurrentUser,
    service: BookServiceDep,
    q: Annotated[str, Query(min_length=1, max_length=256, description="Search text")],
    limit: Annotated[int, Query(ge=1, le=40)] = 20,
) -> BookSearchResults:
    """Search books by title, author, or ISBN."""
    results = await service.search(q, limit=limit)
    return BookSearchResults(query=q, items=results)


@router.get("/{book_id}", response_model=BookMetadata)
async def get_book(
    _user: CurrentUser,
    service: BookServiceDep,
    book_id: str,
) -> BookMetadata:
    """Get normalized metadata for a single book."""
    book = await service.get_book(book_id)
    if book is None:
        raise NotFoundError(
            "The requested book could not be found", code="BOOK_NOT_FOUND"
        )
    return book
