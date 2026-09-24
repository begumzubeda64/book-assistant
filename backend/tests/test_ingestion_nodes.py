"""Tests for the deterministic ingestion nodes."""

from __future__ import annotations

from src.agents.ingestion import nodes


def test_chunk_pages_preserves_page_and_chapter() -> None:
    pages = [
        "Chapter 1 Beginnings\n" + " ".join(["word"] * 500),
        " ".join(["more"] * 100),
    ]
    chunks = nodes.chunk_pages("book1", pages, target_words=220)

    assert len(chunks) >= 3
    # First chunk carries page 1 and the detected chapter.
    assert chunks[0].source.page == 1
    assert chunks[0].source.chapter_title == "Chapter 1 Beginnings"
    assert chunks[0].source.book_id == "book1"
    # Chapter carries forward to page 2 (no new heading there).
    page2 = [c for c in chunks if c.source.page == 2]
    assert page2 and page2[0].source.chapter_title == "Chapter 1 Beginnings"


def test_chunk_pages_skips_empty_pages() -> None:
    chunks = nodes.chunk_pages("b", ["", "   ", "hello world"])
    assert len(chunks) == 1
    assert chunks[0].source.page == 3
    assert chunks[0].word_count == 2


def test_chunk_ids_are_unique_and_stable() -> None:
    pages = [" ".join(["w"] * 500)]
    chunks = nodes.chunk_pages("bookX", pages, target_words=220)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert ids[0] == "bookX:p1:s0"


def test_split_words_respects_target() -> None:
    segments = nodes._split_words(" ".join(["x"] * 45), 20)
    assert [len(s.split()) for s in segments] == [20, 20, 5]
