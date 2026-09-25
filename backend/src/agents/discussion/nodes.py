"""Deterministic discussion nodes.

Build a grounded prompt from retrieved passages + conversation context, and turn
retrieved passages into citations. The answer must be grounded only in the
retrieved source material; citations are taken from retrieval metadata and never
fabricated (security.md).
"""

from __future__ import annotations

from src.agents.shared.ports import RetrievedPassage

# How many prior turns of context to include in the prompt.
CONTEXT_TURN_LIMIT = 6


def build_grounded_prompt(
    question: str,
    passages: list[RetrievedPassage],
    history: list[tuple[str, str]],
) -> str:
    """Build a grounded answer prompt from context + retrieved sources."""
    recent = history[-CONTEXT_TURN_LIMIT:]
    history_block = "\n".join(f"{role}: {content}" for role, content in recent)
    source_block = "\n\n".join(
        f"[{p.chunk_id or i}] {p.text}" for i, p in enumerate(passages)
    )
    return (
        "You are a book companion answering questions about a book.\n"
        "Answer ONLY using the source material below. If the sources do not "
        "contain the answer, say you cannot find it in the book. Do not invent "
        "facts or citations.\n\n"
        f"CONVERSATION SO FAR:\n{history_block or '(none)'}\n\n"
        f"SOURCE MATERIAL:\n{source_block or '(no relevant sources found)'}\n\n"
        f"QUESTION: {question}"
    )


def passages_to_citations(passages: list[RetrievedPassage]) -> list[dict[str, object]]:
    """Distinct citations derived from retrieved passages (never fabricated)."""
    seen: set[tuple[object, object, object]] = set()
    citations: list[dict[str, object]] = []
    for passage in passages:
        key = (passage.chapter_title, passage.section, passage.page)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "chunk_id": passage.chunk_id,
                "chapter_title": passage.chapter_title,
                "section": passage.section,
                "page": passage.page,
            }
        )
    return citations
