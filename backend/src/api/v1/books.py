"""Book discovery endpoints.

    GET /api/v1/books/search
    GET /api/v1/books/{book_id}

Implemented in task group 5 (book discovery). These are declared stubs so the
API surface and OpenAPI docs reflect the design.
"""

from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/search", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def search_books(q: str) -> dict[str, str]:
    """Search books by title, author, or ISBN (not yet implemented)."""
    return {"detail": "not_implemented"}


@router.get("/{book_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_book(book_id: str) -> dict[str, str]:
    """Get normalized metadata for a book (not yet implemented)."""
    return {"detail": "not_implemented"}
