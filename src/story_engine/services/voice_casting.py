"""Assigns each script character a voice from the curated reference-voice library.

Deliberately does NOT clone any real/named person's actual voice (see
task discussion): the LLM is only asked to judge a character's *archetype*
(gender presentation, age group, tone) from how they're written, and that
archetype is matched against `indicf5_tts/voice_library.json` — a small set
of generic reference clips this project owns, none of them an identifiable
public figure's recording. This mirrors `services/cast_proposal.py`'s
posture: bounded structured-JSON output, parsed defensively, never trusted
blindly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from story_engine.agents.prompts.system import COMMON_BOUNDARY
from story_engine.agents.provider import ModelProvider, ModelProviderError
from story_engine.security.prompt_safety import UnsafePromptInput, delimit_untrusted_text

_VOICE_LIBRARY_PATH = (
    Path(__file__).resolve().parents[3] / "indicf5_tts" / "voice_library.json"
)

_GENDERS = {"female", "male", "neutral"}
_AGE_GROUPS = {"young", "adult", "elder"}

_VOICE_CASTING_SYSTEM_PROMPT = (
    "VoiceCasting v1: Given a story's scene text and a list of character names who "
    "speak in it, judge each character's voice archetype from how they are written "
    "(their dialogue, action beats, and any age/role cues in the text) — never from "
    "the character's real-world name resembling anyone famous. "
    "Respond with ONLY a JSON array (no prose, no markdown fences). Each element must "
    "be an object with exactly these fields: "
    '"name" (must exactly match one of the given character names), '
    '"gender" (one of "female", "male", "neutral"), '
    '"age_group" (one of "young", "adult", "elder"), '
    '"tone" (a short comma-separated description of vocal tone/manner, e.g. '
    '"stern, blunt" or "warm, expressive"). '
    f"{COMMON_BOUNDARY}"
)


class VoiceArchetype(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    gender: str
    age_group: str
    tone: str = Field(default="", max_length=200)


@dataclass(frozen=True)
class VoiceLibraryEntry:
    id: str
    file: str
    gender: str
    age_group: str
    tone: str
    ref_text: str | None


class VoiceCastingError(ValueError):
    """Raised when the LLM's voice-archetype proposal is malformed."""


@lru_cache(maxsize=1)
def load_voice_library() -> list[VoiceLibraryEntry]:
    """Load the curated reference-voice library, skipping entries with no verified ref_text.

    An entry with `ref_text: null` has not had its reference clip's transcript
    verified (see `scripts/fill_voice_library_ref_text.py`) — using it would
    hand IndicF5 a wrong conditioning transcript, which degrades cloning
    quality silently, so such entries are excluded rather than guessed at.
    """

    raw = json.loads(_VOICE_LIBRARY_PATH.read_text(encoding="utf-8"))
    entries = []
    for voice in raw["voices"]:
        if not voice.get("ref_text"):
            continue
        entries.append(
            VoiceLibraryEntry(
                id=voice["id"],
                file=voice["file"],
                gender=voice["gender"],
                age_group=voice["age_group"],
                tone=voice.get("tone", ""),
                ref_text=voice["ref_text"],
            )
        )
    if not entries:
        raise VoiceCastingError(
            "No voice library entries have a verified ref_text; run "
            "scripts/fill_voice_library_ref_text.py first."
        )
    return entries


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json_array(raw: str) -> str:
    cleaned = _strip_code_fences(raw)
    start, end = cleaned.find("["), cleaned.rfind("]")
    return cleaned[start : end + 1] if start >= 0 and end > start else cleaned


def parse_and_validate_archetypes(
    raw_output: str, expected_names: list[str]
) -> dict[str, VoiceArchetype]:
    cleaned = _extract_json_array(raw_output)
    try:
        parsed: Any = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise VoiceCastingError("The voice casting proposal was not valid JSON.") from error

    if not isinstance(parsed, list):
        raise VoiceCastingError("The voice casting proposal must be a JSON array.")

    by_name: dict[str, VoiceArchetype] = {}
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise VoiceCastingError(f"Character {index} was not a JSON object.")
        allowed_keys = {"name", "gender", "age_group", "tone"}
        sanitized_item = {k: v for k, v in item.items() if k in allowed_keys}
        try:
            archetype = VoiceArchetype(**sanitized_item)
        except ValidationError as error:
            raise VoiceCastingError(f"Character {index} had an invalid shape: {error}") from error
        if archetype.gender not in _GENDERS or archetype.age_group not in _AGE_GROUPS:
            continue
        if archetype.name in expected_names:
            by_name[archetype.name] = archetype

    return by_name


def _fallback_archetype(name: str) -> VoiceArchetype:
    """Deterministic fallback so every character always gets *some* archetype."""

    return VoiceArchetype(name=name, gender="neutral", age_group="adult", tone="")


def propose_voice_archetypes(
    *,
    provider: ModelProvider,
    model: str,
    scene_text: str,
    character_names: list[str],
) -> dict[str, VoiceArchetype]:
    """Call the model once to judge each character's voice archetype.

    Falls back to a neutral archetype per character (never raises up to the
    caller) if the provider is unavailable or returns something unusable —
    voice casting is a presentation concern, not something that should block
    audio generation entirely.
    """

    if not character_names:
        return {}

    try:
        user_data = delimit_untrusted_text(
            f"Characters: {', '.join(character_names)}\nScene text:\n{scene_text}",
            source="voice_casting",
        )
        raw_output = provider.complete(
            system_prompt=_VOICE_CASTING_SYSTEM_PROMPT, user_data=user_data, model=model
        )
        archetypes = parse_and_validate_archetypes(raw_output, character_names)
    except (ModelProviderError, VoiceCastingError, UnsafePromptInput):
        archetypes = {}

    for name in character_names:
        archetypes.setdefault(name, _fallback_archetype(name))
    return archetypes


def _score(entry: VoiceLibraryEntry, archetype: VoiceArchetype) -> int:
    score = 0
    if archetype.gender != "neutral" and entry.gender == archetype.gender:
        score += 2
    if entry.age_group == archetype.age_group:
        score += 1
    return score


def match_voice(archetype: VoiceArchetype, library: list[VoiceLibraryEntry]) -> VoiceLibraryEntry:
    """Pick the best-matching library voice, deterministically, with a stable tiebreak."""

    return max(library, key=lambda entry: (_score(entry, archetype), entry.id))


def cast_voices(
    *,
    provider: ModelProvider,
    model: str,
    scene_text: str,
    character_names: list[str],
) -> dict[str, VoiceLibraryEntry]:
    """End-to-end: judge archetypes, then map each character to a library voice."""

    library = load_voice_library()
    archetypes = propose_voice_archetypes(
        provider=provider, model=model, scene_text=scene_text, character_names=character_names
    )
    return {name: match_voice(archetype, library) for name, archetype in archetypes.items()}
