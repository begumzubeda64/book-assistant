"""Transparent recommendation scoring.

A deliberately simple, explainable scoring function (not a learned recommender
model — see development.md / decisions.md). Each signal contributes an additive,
weighted amount, and the reason text is derived from whichever signals fired, so
every recommendation can be explained.

Formula (per candidate book, against the user's signals):

    score =  W_CATEGORY * (matching categories / candidate categories)
           + W_AUTHOR   * (1 if any author matches else 0)
           + W_CONCEPT  * (matching saved concepts, capped)
    where matches are case-insensitive.

Books the user already started or completed are excluded upstream (not scored).
Weights are module constants so they are visible and tunable.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.recommendations import UserSignals
from src.schemas.books import BookMetadata

# Additive weights. Category affinity dominates, author is a strong secondary,
# saved-concept overlap is a bonus.
W_CATEGORY = 3.0
W_AUTHOR = 2.0
W_CONCEPT = 1.0
# Cap how much saved-concept overlap can contribute so it can't dominate.
MAX_CONCEPT_MATCHES = 3


@dataclass
class ScoredBook:
    score: float
    reason: str


def _lower_set(values: list[str]) -> set[str]:
    return {v.strip().lower() for v in values if v.strip()}


def score_book(book: BookMetadata, signals: UserSignals) -> ScoredBook:
    """Score a candidate book against the user's signals; returns score + reason."""
    reasons: list[str] = []
    score = 0.0

    categories = _lower_set(book.categories)
    if categories:
        matches = categories & signals.preferred_categories
        if matches:
            score += W_CATEGORY * (len(matches) / len(categories))
            sample = sorted(matches)[0]
            reasons.append(f"matches a category you read ({sample})")

    authors = _lower_set(book.authors)
    if authors & signals.preferred_authors:
        score += W_AUTHOR
        reasons.append("by an author you've read")

    text = f"{book.title} {book.description or ''}".lower()
    concept_hits = sorted(c for c in signals.saved_concepts if c and c in text)
    if concept_hits:
        capped = min(len(concept_hits), MAX_CONCEPT_MATCHES)
        score += W_CONCEPT * capped
        reasons.append(f"relates to a concept you saved ({concept_hits[0]})")

    reason = "; ".join(reasons) if reasons else "similar to books in your library"
    return ScoredBook(score=round(score, 4), reason=reason.capitalize())
