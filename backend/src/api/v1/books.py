"""Book discovery endpoints.

    GET /api/v1/books/search
    GET /api/v1/books/{book_id}

Returns normalized, provider-agnostic metadata with legitimate discovery links.
The underlying book is never ingested from these links (requirement 2.4).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from src.api.dependencies import (
    BookDeletionServiceDep,
    BookServiceDep,
    CurrentUser,
)
from src.core.errors import NotFoundError
from src.core.logging import get_logger
from src.schemas.books import BookMetadata, BookSearchResults

logger = get_logger(__name__)

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


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    user: CurrentUser,
    service: BookDeletionServiceDep,
    book_id: str,
) -> None:
    """Delete all of the authenticated user's content for a book.

    Removes the uploaded PDF, prepared chunks + KB/GraphRAG data, reading
    results, conversations, and progress — scoped to the caller's own content.
    Job records and logs are preserved as the audit trail; the deletion itself
    is audit-logged. Idempotent: deleting an already-absent book still returns
    204.
    """
    summary = service.delete_book(user_id=user.user_id, book_id=book_id)
    logger.info("book_delete_requested", extra={"book_id": book_id, **summary})
