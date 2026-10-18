"""Deterministic adaptive-reading nodes.

All of these are plain algorithms (no model): compute the word budget, treat the
book's prepared chunks as sections, rank them by importance, select to the
budget, build the generation prompt, validate the model output, and attach
source references. Only the prose-generation step (in the graph) calls the
model.

Ranking uses multiple signals — position, heading/chapter presence,
argument/evidence indicators, term centrality, and relatedness to the requested
focus — rather than taking the first N words (design.md).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from src.agents.shared.types import PreparedChunk
from src.models.reading import (
    ReadingFocus,
    ReadingMode,
    word_budget_for_minutes,
)

# Signal cue words.
_ARGUMENT_CUES = (
    "because",
    "therefore",
    "thus",
    "however",
    "argue",
    "argues",
    "claim",
    "reason",
    "evidence",
    "shows",
    "conclude",
    "hence",
    "consequently",
)
_EXAMPLE_CUES = ("example", "for instance", "such as", "e.g.", "case", "illustrat")

# Words to ignore when computing term centrality.
_STOPWORDS = frozenset(
    (  # noqa: SIM905 - readable wrapped form preferred over a long list literal
        "the a an and or but of to in on for with as at by is are was were be "
        "been it its this that these those from we you they he she i not can "
        "will would should could may might their our your his her them us if "
        "then than so such into about over under more most some any all one "
        "two three"
    ).split()
)

# Per-focus keyword affinity, used as one ranking signal.
_FOCUS_KEYWORDS: dict[ReadingFocus, tuple[str, ...]] = {
    ReadingFocus.KEY_ARGUMENTS: _ARGUMENT_CUES,
    ReadingFocus.EXAMPLES: _EXAMPLE_CUES,
    ReadingFocus.PRACTICAL_TAKEAWAYS: ("should", "step", "how to", "apply", "practice"),
    ReadingFocus.KEY_IDEAS: ("idea", "concept", "principle", "key", "central"),
    ReadingFocus.CONCEPT_EXPLANATION: ("means", "defined", "definition", "concept"),
}


@dataclass
class RankedSection:
    chunk: PreparedChunk
    score: float


def word_budget(minutes: int) -> int:
    """Target word count for the reading duration (150 WPM default)."""
    return word_budget_for_minutes(minutes)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def _term_frequencies(chunks: list[PreparedChunk]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for chunk in chunks:
        for token in _tokenize(chunk.text):
            if token not in _STOPWORDS and len(token) > 2:
                counter[token] += 1
    return counter


def _cue_hits(text: str, cues: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(lowered.count(cue) for cue in cues)


def rank_sections(
    chunks: list[PreparedChunk],
    *,
    focus: ReadingFocus,
) -> list[RankedSection]:
    """Score each section (chunk) by importance. Higher is more important."""
    if not chunks:
        return []

    global_tf = _term_frequencies(chunks)
    total = len(chunks)
    focus_cues = _FOCUS_KEYWORDS.get(focus, ())

    ranked: list[RankedSection] = []
    for index, chunk in enumerate(chunks):
        tokens = [
            t for t in _tokenize(chunk.text) if t not in _STOPWORDS and len(t) > 2
        ]
        words = max(len(tokens), 1)

        # Position: earlier sections carry framing weight (gentle decay).
        position_score = 1.0 - (index / total) * 0.5

        # Headings/chapters: a chunk that starts a chapter is structurally salient.
        heading_score = 0.3 if chunk.source.chapter_title else 0.0

        # Argument/evidence density (normalized by length).
        argument_score = _cue_hits(chunk.text, _ARGUMENT_CUES) / words

        # Centrality: mean global frequency of this chunk's terms.
        centrality = (
            sum(global_tf[t] for t in tokens) / words if tokens else 0.0
        )
        centrality_score = math.log1p(centrality)

        # Focus relatedness.
        focus_score = (
            _cue_hits(chunk.text, focus_cues) / words if focus_cues else 0.0
        )

        score = (
            0.30 * position_score
            + heading_score
            + 2.0 * argument_score
            + 0.50 * centrality_score
            + 2.0 * focus_score
        )
        ranked.append(RankedSection(chunk=chunk, score=score))

    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked


def select_to_budget(
    ranked: list[RankedSection], *, budget_words: int
) -> list[PreparedChunk]:
    """Select the highest-ranked sections up to the budget, then restore order.

    Selection is by importance, but the selected sections are returned in their
    original reading order so the generated prose stays coherent.
    """
    selected: list[RankedSection] = []
    running = 0
    for section in ranked:
        if running >= budget_words and selected:
            break
        selected.append(section)
        running += section.chunk.word_count or len(section.chunk.text.split())

    # Restore original order by (page, chunk_id) for coherent narrative flow.
    selected.sort(
        key=lambda r: (r.chunk.source.page or 0, r.chunk.chunk_id)
    )
    return [r.chunk for r in selected]


def build_prompt(
    chunks: list[PreparedChunk],
    *,
    mode: ReadingMode,
    focus: ReadingFocus,
    budget_words: int,
) -> str:
    """Build the generation prompt from selected sections (system-separated)."""
    depth = {
        ReadingMode.QUICK_READ: (
            "the single central idea and its most important argument"
        ),
        ReadingMode.BALANCED_READ: (
            "the major arguments, key explanations, examples, and context"
        ),
        ReadingMode.DEEP_READ: (
            "the important arguments, evidence, relationships, and nuance"
        ),
    }[mode]
    source_block = "\n\n".join(f"[{c.chunk_id}] {c.text}" for c in chunks)
    return (
        "You are condensing this specific book into coherent, engaging prose "
        "that preserves what makes it worth reading — not a generic overview.\n\n"
        f"FOCUS: {focus.value}. Cover {depth}.\n"
        f"LENGTH: about {budget_words} words of flowing prose (no bullet points, "
        "no headings unless the source is clearly structured that way, no "
        "truncation).\n\n"
        "WRITE IT WELL:\n"
        "- Keep the book's CONCRETE specifics: the actual names, examples, "
        "stories, data, and distinctive terminology it uses. These specifics are "
        "what stop a reading from sounding generic — do not flatten them into "
        "vague generalities.\n"
        "- Preserve the author's framing and line of reasoning, so the argument "
        "still builds the way it does in the book.\n"
        "- Use plain, direct language. Avoid filler and empty phrases like "
        "'this book explores various important themes' — say what it actually "
        "says.\n"
        "- Read as one connected piece, not a list of disconnected points.\n\n"
        "GROUNDING: Use ONLY the provided source material below; do not add "
        "outside facts, and do not invent specifics.\n\n"
        f"SOURCE MATERIAL:\n{source_block}"
    )


def validate_output(text: str, *, budget_words: int) -> str:
    """Validate the generated reading is coherent prose within tolerance.

    Rejects empty output and obvious bullet dumps; allows the word count to
    deviate from the budget to preserve coherence (design.md).
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError("Generated reading is empty")

    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    bullet_lines = sum(1 for ln in lines if ln[:1] in {"-", "*", "•"})
    if lines and bullet_lines / len(lines) > 0.5:
        raise ValueError("Generated reading is a bullet dump, not prose")

    words = len(stripped.split())
    # Generous bounds: coherence beats hitting the exact budget.
    if words > budget_words * 2.5:
        raise ValueError("Generated reading far exceeds the target length")
    return stripped


def dedupe_source_refs(chunks: list[PreparedChunk]) -> list[dict[str, object]]:
    """Distinct source references from the selected sections."""
    seen: set[tuple[str | None, str | None, int | None]] = set()
    refs: list[dict[str, object]] = []
    for chunk in chunks:
        key = (
            chunk.source.chapter_title,
            chunk.source.section,
            chunk.source.page,
        )
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "chapter_title": chunk.source.chapter_title,
                "section": chunk.source.section,
                "page": chunk.source.page,
            }
        )
    return refs
