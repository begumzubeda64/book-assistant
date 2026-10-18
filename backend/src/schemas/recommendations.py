"""Recommendation API schemas."""

from __future__ import annotations

from pydantic import Field

from src.schemas.base import APIModel
from src.schemas.books import BookMetadata


class RecommendationItem(APIModel):
    """A recommended book with a transparent score and a concise reason."""

    book: BookMetadata
    score: float = Field(..., description="Transparent recommendation score")
    reason: str = Field(..., description="Why this book was recommended")


class RecommendationsResponse(APIModel):
    """Recommended books, most relevant first."""

    items: list[RecommendationItem] = Field(default_factory=list)
