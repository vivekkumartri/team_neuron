"""Unit tests for the Storyteller multilingual prompt-injection helper.

Only the Storyteller's system prompt gets a language instruction (see
`agents/prompts/system.py`'s comment for why Director/World/Evaluator stay
English-only internally). This only checks the instruction text is present
per language, not translation quality or Whisper/TTS output — that is not
verifiable without a live OpenAI call and a native speaker's review (see
task.md).
"""

from __future__ import annotations

import pytest

from story_engine.agents.prompts.system import (
    STORYTELLER,
    storyteller_language_instruction,
    storyteller_prompt_for_language,
)
from story_engine.domain.models import StoryLanguage


@pytest.mark.parametrize(
    ("language", "expected_fragment"),
    [
        (StoryLanguage.ENGLISH, "in English"),
        (StoryLanguage.HINDI, "in Hindi (हिन्दी)"),
        (StoryLanguage.TELUGU, "in Telugu (తెలుగు)"),
    ],
)
def test_language_instruction_names_the_correct_language(
    language: StoryLanguage, expected_fragment: str
) -> None:
    instruction = storyteller_language_instruction(language)
    assert expected_fragment in instruction


@pytest.mark.parametrize("language", list(StoryLanguage))
def test_prompt_for_language_still_contains_the_base_storyteller_prompt(
    language: StoryLanguage,
) -> None:
    prompt = storyteller_prompt_for_language(language)
    assert STORYTELLER in prompt
    assert storyteller_language_instruction(language) in prompt


def test_different_languages_produce_different_prompts() -> None:
    prompts = {language: storyteller_prompt_for_language(language) for language in StoryLanguage}
    assert len(set(prompts.values())) == len(StoryLanguage)
