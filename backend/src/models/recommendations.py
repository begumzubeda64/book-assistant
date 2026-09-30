"""Recommendation domain types.

The signals a user's recommendations are scored against. These are gathered from
data already available in the MVP (reading progress, uploaded/started/completed
books, saved concepts, and the categories/authors of books the user engaged
with). Kept explicit so the scoring stays transparent and testable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserSignals(BaseModel):
    """Behavioral and preference signals for one user."""

    # Categories/authors from books the user has engaged with (lowercased).
    preferred_categories: set[str] = Field(default_factory=set)
    preferred_authors: set[str] = Field(default_factory=set)
    # Concepts the user explicitly saved (lowercased).
    saved_concepts: set[str] = Field(default_factory=set)
    # Book ids the user has started and completed (to avoid re-recommending).
    started_book_ids: set[str] = Field(default_factory=set)
    completed_book_ids: set[str] = Field(default_factory=set)
