"""Discussion graph state."""

from __future__ import annotations

from typing import TypedDict

from src.agents.shared.ports import RetrievedPassage


class DiscussionState(TypedDict, total=False):
    """State threaded through the discussion graph."""

    # Inputs
    user_id: str
    book_id: str
    question: str
    history: list[tuple[str, str]]  # (role, content) prior turns

    # Populated by nodes
    passages: list[RetrievedPassage]
    prompt: str
    answer: str
    citations: list[dict[str, object]]
