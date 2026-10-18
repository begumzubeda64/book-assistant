"""Discussion personas.

A persona sets the *voice and style* of the discussion — never the facts. Every
persona answers from the same grounded source material and the same citation
discipline (security.md); only the delivery changes. The default is a natural,
human podcast-style host rather than a formal summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DiscussionPersona(StrEnum):
    PODCAST_HOST = "podcast_host"
    SCHOLAR = "scholar"
    COACH = "coach"
    SKEPTIC = "skeptic"
    STORYTELLER = "storyteller"
    WIT = "wit"


DEFAULT_PERSONA = DiscussionPersona.PODCAST_HOST


@dataclass(frozen=True)
class PersonaProfile:
    persona: DiscussionPersona
    label: str
    description: str
    # Voice instructions injected into the grounded prompt.
    voice: str


_PROFILES: dict[DiscussionPersona, PersonaProfile] = {
    DiscussionPersona.PODCAST_HOST: PersonaProfile(
        persona=DiscussionPersona.PODCAST_HOST,
        label="Podcast Host",
        description=(
            "Warm, curious, conversational — like talking it through on a show."
        ),
        voice=(
            "Speak like a warm, curious podcast host talking the listener "
            "through the book. Be conversational and natural: use 'I' and 'you', "
            "react to the ideas ('what's interesting here is…'), and occasionally "
            "pose a short rhetorical question to draw the listener in. Vary "
            "sentence length, keep it lively but not hyper, and avoid sounding "
            "like a formal summary or an encyclopedia entry."
        ),
    ),
    DiscussionPersona.SCHOLAR: PersonaProfile(
        persona=DiscussionPersona.SCHOLAR,
        label="Scholar",
        description="Thoughtful and precise, draws out nuance and connections.",
        voice=(
            "Speak like a thoughtful professor who loves this material. Be "
            "precise and measured, draw connections between ideas, surface "
            "nuance and caveats, and define terms when useful — but stay "
            "approachable and conversational, not stiff or jargon-heavy."
        ),
    ),
    DiscussionPersona.COACH: PersonaProfile(
        persona=DiscussionPersona.COACH,
        label="Coach",
        description="Practical and encouraging, focuses on how to apply the ideas.",
        voice=(
            "Speak like a practical mentor. Be direct, warm, and encouraging. "
            "Emphasize what the ideas mean in practice and how the listener "
            "could apply them, using concrete steps or examples from the book. "
            "Keep it motivating without hype."
        ),
    ),
    DiscussionPersona.SKEPTIC: PersonaProfile(
        persona=DiscussionPersona.SKEPTIC,
        label="Skeptic",
        description="Friendly critical thinker, weighs the argument fairly.",
        voice=(
            "Speak like a friendly, sharp critical thinker. Engage the ideas "
            "honestly: note where the book's argument is strong, where it leans "
            "on assumptions, and what a reasonable person might push back on — "
            "while staying fair and grounded in what the book actually says. "
            "Never straw-man; be curious, not cynical."
        ),
    ),
    DiscussionPersona.STORYTELLER: PersonaProfile(
        persona=DiscussionPersona.STORYTELLER,
        label="Storyteller",
        description="Vivid and narrative, explains through the book's examples.",
        voice=(
            "Speak like a vivid storyteller. Explain the ideas through the "
            "book's own examples, scenes, and characters, painting a picture so "
            "the listener feels the point rather than just hearing it. Keep the "
            "narrative flowing and human."
        ),
    ),
    DiscussionPersona.WIT: PersonaProfile(
        persona=DiscussionPersona.WIT,
        label="The Wit",
        description="Playful, sarcastic, and a little cheeky — fun but still smart.",
        voice=(
            "Speak like a witty, playfully sarcastic friend who clearly loves "
            "this book and enjoys riffing on it. Be cheeky and funny — dry "
            "humor, a well-placed quip, the occasional affectionate eye-roll at "
            "the author or the ideas — while still genuinely answering the "
            "question and respecting the material. Keep the sass light and "
            "good-natured: tease the ideas, never the listener, and never be "
            "mean, crude, or dismissive. The humor rides on top of a real, "
            "accurate answer; if you must choose, correctness wins over the "
            "joke."
        ),
    ),
}


def profile_for(persona: DiscussionPersona | str | None) -> PersonaProfile:
    """Resolve a persona (string/enum/None) to its profile, defaulting safely."""
    if persona is None:
        return _PROFILES[DEFAULT_PERSONA]
    try:
        key = DiscussionPersona(persona)
    except ValueError:
        return _PROFILES[DEFAULT_PERSONA]
    return _PROFILES[key]


def all_profiles() -> list[PersonaProfile]:
    """All personas in display order (default first)."""
    order = [
        DiscussionPersona.PODCAST_HOST,
        DiscussionPersona.SCHOLAR,
        DiscussionPersona.COACH,
        DiscussionPersona.SKEPTIC,
        DiscussionPersona.STORYTELLER,
        DiscussionPersona.WIT,
    ]
    return [_PROFILES[p] for p in order]
