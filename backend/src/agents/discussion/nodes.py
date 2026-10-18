"""Deterministic discussion nodes.

Build a grounded prompt from retrieved passages + conversation context, and turn
retrieved passages into citations. The answer must be grounded only in the
retrieved source material; citations are taken from retrieval metadata and never
fabricated (security.md).
"""

from __future__ import annotations

from src.agents.shared.ports import RetrievedPassage

# How many of the most recent turns to include verbatim in the prompt. Older
# turns are folded into a running summary (see summarize_history) to keep long
# conversations within the model context window.
CONTEXT_TURN_LIMIT = 6

# Summarize once the thread grows beyond this many turns.
SUMMARY_THRESHOLD = CONTEXT_TURN_LIMIT


def build_grounded_prompt(
    question: str,
    passages: list[RetrievedPassage],
    history: list[tuple[str, str]],
    summary: str | None = None,
) -> str:
    """Build a grounded answer prompt from summary + recent turns + sources."""
    recent = history[-CONTEXT_TURN_LIMIT:]
    history_block = "\n".join(f"{role}: {content}" for role, content in recent)
    source_block = "\n\n".join(
        f"[{p.chunk_id or i}] {p.text}" for i, p in enumerate(passages)
    )
    summary_block = (
        f"EARLIER CONVERSATION SUMMARY:\n{summary}\n\n" if summary else ""
    )
    return (
        "You are a book companion answering questions about a book. Use the "
        "earlier conversation summary and recent turns for context, but ground "
        "every factual claim in the SOURCE MATERIAL below. If the sources do "
        "not contain the answer, say you cannot find it in the book. Do not "
        "invent facts or citations.\n\n"
        f"{summary_block}"
        f"RECENT CONVERSATION:\n{history_block or '(none)'}\n\n"
        f"SOURCE MATERIAL:\n{source_block or '(no relevant sources found)'}\n\n"
        f"QUESTION: {question}"
    )


# Re-evaluate the title during the opening turns so a casual opener ("hi") gets
# replaced once a real topic emerges; after this it stays stable.
TITLE_REFRESH_TURNS = 6  # ~3 exchanges (user+assistant)


def build_title_prompt(history: list[tuple[str, str]], question: str) -> str:
    """Prompt for a very short, intent-based conversation title (2-3 words)."""
    recent = history[-TITLE_REFRESH_TURNS:]
    convo = "\n".join(f"{role}: {content}" for role, content in recent)
    return (
        "Give a 2-3 word title (max ~4 words) capturing the TOPIC/intent of "
        "this book discussion. If it's just small talk or a greeting with no "
        'real topic yet, answer exactly "General chat". Return only the title, '
        "no quotes, no punctuation at the end.\n\n"
        f"CONVERSATION:\n{convo}\nuser: {question}\n\nTITLE:"
    )


def clean_title(raw: str) -> str:
    """Normalize a model-generated title to a short, clean label."""
    text = " ".join(raw.strip().strip('"').strip().split())
    words = text.split()
    if len(words) > 5:
        text = " ".join(words[:5])
    return text[:60] or "Discussion"


# Placeholder titles that carry no real topic yet. While the current title is
# one of these, we keep (re)generating on each turn so the first real topic
# replaces it, even past the normal opening-turns window ("replace the title if
# context was not enough").
_GENERIC_TITLES = {"general chat", "discussion", "new discussion", ""}


def is_generic_title(title: str | None) -> bool:
    """True when the title is still a placeholder (no real topic captured)."""
    return (title or "").strip().lower() in _GENERIC_TITLES


def build_summary_prompt(
    prior_summary: str | None, aged_out: list[tuple[str, str]]
) -> str:
    """Prompt to roll older turns into a concise running summary."""
    turns = "\n".join(f"{role}: {content}" for role, content in aged_out)
    prior = f"PREVIOUS SUMMARY:\n{prior_summary}\n\n" if prior_summary else ""
    return (
        "Summarize the following book discussion so a later turn has the "
        "important context. Keep it concise (a few sentences), factual, and "
        "focused on what was asked and concluded. Merge with the previous "
        "summary if present.\n\n"
        f"{prior}NEW TURNS TO FOLD IN:\n{turns}\n\nUPDATED SUMMARY:"
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
