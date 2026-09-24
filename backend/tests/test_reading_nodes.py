"""Tests for the deterministic adaptive-reading nodes."""

from __future__ import annotations

import pytest
from src.agents.adaptive_reading import nodes
from src.agents.shared.types import PreparedChunk, SourceRef
from src.models.reading import ReadingFocus, ReadingMode


def _chunk(chunk_id: str, text: str, page: int, chapter: str | None = None):
    return PreparedChunk(
        chunk_id=chunk_id,
        text=text,
        word_count=len(text.split()),
        source=SourceRef(book_id="b", page=page, chapter_title=chapter),
    )


def test_word_budget_targets() -> None:
    assert nodes.word_budget(3) == 450
    assert nodes.word_budget(5) == 750
    assert nodes.word_budget(10) == 1500


def test_ranking_is_not_first_n() -> None:
    # A weak intro chunk first, then a strong argument-dense chunk later.
    weak = _chunk("b:p1:s0", "some words here " * 20, 1)
    strong = _chunk(
        "b:p5:s0",
        "Therefore the evidence shows that because of this we conclude the claim. "
        * 15,
        5,
    )
    ranked = nodes.rank_sections([weak, strong], focus=ReadingFocus.KEY_ARGUMENTS)
    # The argument-dense chunk should outrank the earlier weak intro.
    assert ranked[0].chunk.chunk_id == "b:p5:s0"


def test_select_to_budget_limits_and_restores_order() -> None:
    chunks = [_chunk(f"b:p{i}:s0", "word " * 100, i) for i in range(1, 6)]
    ranked = nodes.rank_sections(chunks, focus=ReadingFocus.KEY_IDEAS)
    selected = nodes.select_to_budget(ranked, budget_words=250)
    # ~250 words / 100 per chunk -> around 3 chunks selected.
    assert 2 <= len(selected) <= 4
    # Returned in original reading order (by page).
    pages = [c.source.page for c in selected]
    assert pages == sorted(pages)


def test_validate_output_accepts_prose() -> None:
    text = "This is a coherent paragraph of prose. " * 10
    assert nodes.validate_output(text, budget_words=100).startswith("This is")


def test_validate_output_rejects_empty() -> None:
    with pytest.raises(ValueError):
        nodes.validate_output("   ", budget_words=100)


def test_validate_output_rejects_bullet_dump() -> None:
    bullets = "\n".join(f"- point {i}" for i in range(10))
    with pytest.raises(ValueError):
        nodes.validate_output(bullets, budget_words=100)


def test_validate_output_rejects_gross_overrun() -> None:
    text = "word " * 500
    with pytest.raises(ValueError):
        nodes.validate_output(text, budget_words=100)


def test_dedupe_source_refs() -> None:
    chunks = [
        _chunk("b:p1:s0", "x", 1, "Chapter 1"),
        _chunk("b:p1:s1", "y", 1, "Chapter 1"),
        _chunk("b:p2:s0", "z", 2, "Chapter 2"),
    ]
    refs = nodes.dedupe_source_refs(chunks)
    # (Chapter1,p1) collapses to one; Chapter2/p2 is distinct.
    assert len(refs) == 2


def test_build_prompt_includes_sources_and_focus() -> None:
    chunks = [_chunk("b:p1:s0", "content here", 1)]
    prompt = nodes.build_prompt(
        chunks,
        mode=ReadingMode.BALANCED_READ,
        focus=ReadingFocus.KEY_ARGUMENTS,
        budget_words=450,
    )
    assert "key_arguments" in prompt
    assert "b:p1:s0" in prompt
    assert "450" in prompt
