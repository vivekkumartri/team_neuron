"""LLM-driven starting-cast proposal (task.md Task 4H.2 gap closure).

This module produces a *proposal* only — nothing here writes to the
database. The proposed characters are returned to the client, where the
author can edit, add, or remove entries before ever calling
`POST /stories` (which is what actually creates `entities` rows). This
mirrors the same untrusted-data / no-early-commit posture used by the
`agents/` adapters (`agents/base.py`'s `ProposalAgent.propose`), but this is
a plain service function rather than a `ProposalAgent` subclass because a
cast proposal is a one-shot structured-JSON generation, not an in-story
beat proposal that flows through `security/prompt_safety.py`'s
`AgentProposal`/`ProposalAction` machinery.

Deliberately NOT ported from `docs/reference/StoryEngineProto.jsx`'s
`CAST_INITIAL`/`ScreenCharacters` (see task.md 0.4):
  - No `hidden` characteristic field. Every field this module can produce
    (`name`, `role`, `voice`, `traits`, `visual`) is meant to be shown to
    the user and is editable, matching Task 2D's "inspectable mutable
    trait state" decision — there is no concealed/blurred property here.
  - No 20-character seed minimum — this module accepts whatever seed text
    already passed `SeedForm.tsx`'s soft clarification prompt; it does not
    itself gate on seed length.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from story_engine.agents.prompts.system import COMMON_BOUNDARY
from story_engine.agents.provider import ModelProvider, ModelProviderError
from story_engine.domain.models import StoryLanguage
from story_engine.security.prompt_safety import delimit_untrusted_text

_MIN_CHARACTERS = 1
_MAX_CHARACTERS = 6
_TARGET_CHARACTERS_HINT = "2 to 4"

_CAST_PROPOSAL_SYSTEM_PROMPT = (
    "CastProposal v1: Given a short story seed, propose between 2 and 4 starting "
    "characters for the cast, the first of whom must be the protagonist. "
    "Respond with ONLY a JSON array (no prose, no markdown fences). Each element "
    "must be an object with exactly these string fields: "
    '"name" (a proper name), '
    '"role" (a short descriptor, e.g. "Protagonist · Rogue Watchmaker"; the '
    "first character's role must clearly indicate they are the protagonist), "
    '"voice" (their dialogue style), '
    '"traits" (comma-separated core personality traits), '
    '"visual" (comma-separated visual attributes). '
    "Do not include any hidden, secret, or concealed fields — every field you "
    f"return is shown directly to the author. {COMMON_BOUNDARY}"
)


class CastCharacterProposal(BaseModel):
    """One sanitized, bounded character proposal. No hidden/secret field."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    voice: str = Field(default="", max_length=200)
    traits: str = Field(default="", max_length=200)
    visual: str = Field(default="", max_length=200)


class CastProposalError(ValueError):
    """Raised when the LLM's cast proposal is malformed and cannot be trusted."""


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_and_validate_cast_proposal(raw_output: str) -> list[CastCharacterProposal]:
    """Defensively parse and bound the LLM's raw text into a safe cast list.

    Fails closed with a clear `CastProposalError` on: invalid JSON, wrong
    shape, too few/too many characters, a missing protagonist-flagged first
    character, or fields exceeding bounded lengths (each field is also
    truncated/validated by `CastCharacterProposal`'s own `Field` limits, but
    we reject outright rather than silently truncating a bad structural
    shape, since truncation of a wrong shape would hide the real problem).
    """

    cleaned = _strip_code_fences(raw_output)
    try:
        parsed: Any = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise CastProposalError("The cast proposal was not valid JSON.") from error

    if not isinstance(parsed, list):
        raise CastProposalError("The cast proposal must be a JSON array of characters.")
    if len(parsed) < _MIN_CHARACTERS:
        raise CastProposalError("The cast proposal did not include any characters.")
    if len(parsed) > _MAX_CHARACTERS:
        raise CastProposalError(
            f"The cast proposal returned too many characters (max {_MAX_CHARACTERS})."
        )

    characters: list[CastCharacterProposal] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise CastProposalError(f"Character {index} was not a JSON object.")
        # Defensively drop any unexpected field (e.g. a "hidden" field the
        # model invented on its own) before validation rather than letting
        # `extra="forbid"` reject the whole proposal for one stray key.
        allowed_keys = {"name", "role", "voice", "traits", "visual"}
        sanitized_item = {k: v for k, v in item.items() if k in allowed_keys}
        try:
            characters.append(CastCharacterProposal(**sanitized_item))
        except ValidationError as error:
            raise CastProposalError(f"Character {index} had an invalid shape: {error}") from error

    first_role = characters[0].role.lower()
    if "protagonist" not in first_role and "hero" not in first_role and "lead" not in first_role:
        raise CastProposalError(
            "The first proposed character must be clearly flagged as the protagonist."
        )

    return characters


def propose_cast(
    *,
    provider: ModelProvider,
    model: str,
    seed: str,
    language: StoryLanguage = StoryLanguage.ENGLISH,
) -> list[CastCharacterProposal]:
    """Call the model once and return a validated, bounded cast proposal.

    Callers (the `/stories/cast-proposal` route) are responsible for running
    `seed` through `RuleBasedContentPolicy` *before* calling this function —
    this function does not itself gate content, matching the same
    separation `voice.py` uses between the WS transport and the policy
    gate.
    """

    if not seed or not seed.strip():
        raise CastProposalError("A story seed is required to propose a cast.")

    user_data = delimit_untrusted_text(
        f"Seed: {seed.strip()}\nLanguage: {language.value}",
        source="cast_proposal",
    )
    try:
        raw_output = provider.complete(
            system_prompt=_CAST_PROPOSAL_SYSTEM_PROMPT,
            user_data=user_data,
            model=model,
        )
    except ModelProviderError:
        raise

    return parse_and_validate_cast_proposal(raw_output)
