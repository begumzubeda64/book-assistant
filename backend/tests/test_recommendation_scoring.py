"""Tests for the transparent recommendation scoring formula."""

from __future__ import annotations

from src.models.recommendations import UserSignals
from src.schemas.books import BookMetadata
from src.services.recommendation_scoring import (
    W_AUTHOR,
    W_CATEGORY,
    W_CONCEPT,
    score_book,
)


def _book(**kw: object) -> BookMetadata:
    base: dict[str, object] = {
        "book_id": "google_books:1",
        "provider": "google_books",
        "title": "Some Book",
        "authors": [],
        "categories": [],
    }
    base.update(kw)
    return BookMetadata.model_validate(base)


def test_no_signals_yields_zero_score_and_generic_reason() -> None:
    result = score_book(_book(categories=["Fiction"]), UserSignals())
    assert result.score == 0.0
    assert "similar" in result.reason.lower()


def test_category_match_scores_and_explains() -> None:
    book = _book(categories=["Science", "History"])
    signals = UserSignals(preferred_categories={"science"})
    result = score_book(book, signals)
    # 1 of 2 categories match -> W_CATEGORY * 0.5
    assert result.score == round(W_CATEGORY * 0.5, 4)
    assert "category" in result.reason.lower()


def test_author_match_scores_and_explains() -> None:
    book = _book(authors=["Yuval Noah Harari"])
    signals = UserSignals(preferred_authors={"yuval noah harari"})
    result = score_book(book, signals)
    assert result.score == W_AUTHOR
    assert "author" in result.reason.lower()


def test_saved_concept_match_capped() -> None:
    book = _book(
        title="A book about entropy",
        description="entropy entropy chaos order systems",
    )
    signals = UserSignals(saved_concepts={"entropy", "chaos", "order", "systems"})
    result = score_book(book, signals)
    # 4 concepts appear but contribution is capped at 3.
    assert result.score == W_CONCEPT * 3
    assert "concept" in result.reason.lower()


def test_signals_combine_additively() -> None:
    book = _book(
        categories=["Science"],
        authors=["Carl Sagan"],
        title="Cosmos",
        description="the universe",
    )
    signals = UserSignals(
        preferred_categories={"science"},
        preferred_authors={"carl sagan"},
        saved_concepts={"universe"},
    )
    result = score_book(book, signals)
    # category (3*1.0) + author (2.0) + concept (1.0*1)
    assert result.score == round(W_CATEGORY + W_AUTHOR + W_CONCEPT, 4)


def test_matching_is_case_insensitive() -> None:
    book = _book(categories=["SCIENCE"])
    signals = UserSignals(preferred_categories={"science"})
    assert score_book(book, signals).score > 0
