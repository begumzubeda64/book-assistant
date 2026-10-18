"""Tests for discussion personas (voice/style, not facts)."""

from __future__ import annotations

from src.agents.discussion import nodes
from src.agents.discussion.agent import DiscussionAgent
from src.agents.discussion.personas import (
    DEFAULT_PERSONA,
    DiscussionPersona,
    all_profiles,
    profile_for,
)
from src.agents.shared.ports import RetrievedPassage


def test_profile_for_defaults_safely() -> None:
    assert profile_for(None).persona is DEFAULT_PERSONA
    assert profile_for("not_a_persona").persona is DEFAULT_PERSONA
    assert profile_for("scholar").persona is DiscussionPersona.SCHOLAR
    assert profile_for(DiscussionPersona.COACH).persona is DiscussionPersona.COACH


def test_all_profiles_lists_default_first() -> None:
    profiles = all_profiles()
    assert profiles[0].persona is DEFAULT_PERSONA
    # Each profile has a usable label and voice.
    assert all(p.label and p.voice and p.description for p in profiles)


class _RecordingGenerator:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, *, prompt: str, max_words: int) -> str:
        self.prompts.append(prompt)
        return "An answer."

    @property
    def answer_prompt(self) -> str:
        for p in self.prompts:
            if "SOURCE MATERIAL" in p and "TITLE:" not in p:
                return p
        return ""


class _FakeRetriever:
    def __init__(self, passages: list[RetrievedPassage]) -> None:
        self._passages = passages

    def retrieve(self, **_kwargs) -> list[RetrievedPassage]:
        return self._passages


def test_persona_voice_is_injected_into_the_answer_prompt() -> None:
    gen = _RecordingGenerator()
    agent = DiscussionAgent(retriever=_FakeRetriever([]), generator=gen)
    agent.answer(user_id="u1", book_id="b1", question="q", persona="skeptic")
    skeptic_voice = profile_for("skeptic").voice
    # A distinctive fragment of the skeptic voice appears in the prompt.
    assert "critical thinker" in gen.answer_prompt
    assert skeptic_voice[:30] in gen.answer_prompt


def test_default_persona_voice_used_when_unspecified() -> None:
    gen = _RecordingGenerator()
    agent = DiscussionAgent(retriever=_FakeRetriever([]), generator=gen)
    agent.answer(user_id="u1", book_id="b1", question="q")
    assert "podcast host" in gen.answer_prompt.lower()


def test_grounded_prompt_keeps_grounding_rules_with_persona() -> None:
    prompt = nodes.build_grounded_prompt(
        "q", [], [], None, persona_voice="Speak like a coach."
    )
    assert "Speak like a coach." in prompt
    assert "Base every factual claim on the SOURCE MATERIAL" in prompt
