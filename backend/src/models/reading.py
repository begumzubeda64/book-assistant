"""Shared reading enums.

Reading modes map to the ~3/5/10-minute experience (product.md). Defined here so
progress, adaptive reading, and jobs can all reference the same identifiers.
"""

from __future__ import annotations

from enum import StrEnum


class ReadingMode(StrEnum):
    QUICK_READ = "quick_read"
    BALANCED_READ = "balanced_read"
    DEEP_READ = "deep_read"


class ReadingFocus(StrEnum):
    """Content emphasis of an adaptive reading (product.md)."""

    EXECUTIVE_SUMMARY = "executive_summary"
    KEY_IDEAS = "key_ideas"
    KEY_ARGUMENTS = "key_arguments"
    PRACTICAL_TAKEAWAYS = "practical_takeaways"
    EXAMPLES = "examples"
    CHAPTER_SUMMARY = "chapter_summary"
    CONCEPT_EXPLANATION = "concept_explanation"
    NARRATIVE_SUMMARY = "narrative_summary"


# Word-budget targets at the configurable default of 150 WPM (design.md).
DEFAULT_READING_WPM = 150
SUPPORTED_DURATIONS_MINUTES = (3, 5, 10)


def word_budget_for_minutes(minutes: int, *, wpm: int = DEFAULT_READING_WPM) -> int:
    """Target word count for a reading duration (3min≈450, 5≈750, 10≈1500)."""
    return minutes * wpm
