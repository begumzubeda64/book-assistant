"""Recommendation service.

Composes candidate books with the user's signals and scores them with the
transparent scoring function. Candidates and signals are provided via injected
callables so the service is testable and the data sources can evolve without
changing the scoring logic.

Candidates the user has already started or completed are excluded, results are
sorted by score (desc), zero-score items are dropped, and the top N are
returned — each with a concise reason.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.models.recommendations import UserSignals
from src.schemas.books import BookMetadata
from src.schemas.recommendations import RecommendationItem
from src.services.recommendation_scoring import score_book

CandidateProvider = Callable[[UserSignals], Awaitable[list[BookMetadata]]]
SignalsProvider = Callable[[str], Awaitable[UserSignals]]


class RecommendationService:
    def __init__(
        self,
        *,
        signals_provider: SignalsProvider,
        candidate_provider: CandidateProvider,
    ) -> None:
        self._signals = signals_provider
        self._candidates = candidate_provider

    async def recommend(
        self, user_id: str, *, limit: int = 10
    ) -> list[RecommendationItem]:
        signals = await self._signals(user_id)
        candidates = await self._candidates(signals)

        seen = signals.started_book_ids | signals.completed_book_ids
        items: list[RecommendationItem] = []
        for book in candidates:
            if book.book_id in seen:
                continue
            scored = score_book(book, signals)
            if scored.score <= 0:
                continue
            items.append(
                RecommendationItem(
                    book=book, score=scored.score, reason=scored.reason
                )
            )

        items.sort(key=lambda i: i.score, reverse=True)
        return items[:limit]
