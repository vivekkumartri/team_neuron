"""Unit tests for the LLM cast-proposal validator (`services/cast_proposal.py`).

Every case here proves the parser fails closed with a clear
`CastProposalError` rather than crashing or silently accepting a malformed
or unsafe shape, matching the rest of this codebase's defensive posture
toward model output (see `security/prompt_safety.py`).
"""

from __future__ import annotations

import pytest

from story_engine.services.cast_proposal import (
    CastProposalError,
    fallback_cast_from_seed,
    parse_and_validate_cast_proposal,
)

_VALID_TWO_CHARACTER_JSON = (
    '[{"name": "Kaelen", "role": "Protagonist · Rogue Watchmaker", "voice": "Terse", '
    '"traits": "Cautious", "visual": "Grease-stained hands"},'
    '{"name": "Mira", "role": "Guild Enforcer", "voice": "Clipped", '
    '"traits": "Rule-bound", "visual": "Brass mask"}]'
)


def test_valid_proposal_parses_and_bounds_correctly() -> None:
    characters = parse_and_validate_cast_proposal(_VALID_TWO_CHARACTER_JSON)

    assert len(characters) == 2
    assert characters[0].name == "Kaelen"
    assert "Protagonist" in characters[0].role


def test_proposal_wrapped_in_markdown_code_fences_still_parses() -> None:
    fenced = f"```json\n{_VALID_TWO_CHARACTER_JSON}\n```"
    characters = parse_and_validate_cast_proposal(fenced)
    assert len(characters) == 2


def test_proposal_with_an_introductory_sentence_still_parses() -> None:
    characters = parse_and_validate_cast_proposal(
        f"Here is the proposed cast:\n{_VALID_TWO_CHARACTER_JSON}"
    )
    assert len(characters) == 2


def test_malformed_json_fails_closed() -> None:
    with pytest.raises(CastProposalError):
        parse_and_validate_cast_proposal("{not valid json at all")


def test_non_array_json_fails_closed() -> None:
    with pytest.raises(CastProposalError):
        parse_and_validate_cast_proposal('{"name": "Kaelen"}')


def test_empty_array_fails_closed() -> None:
    with pytest.raises(CastProposalError):
        parse_and_validate_cast_proposal("[]")


def test_too_many_characters_fails_closed() -> None:
    one_character = (
        '{"name": "X", "role": "Supporting", "voice": "", "traits": "", "visual": ""}'
    )
    too_many = "[" + ",".join([one_character] * 7) + "]"
    with pytest.raises(CastProposalError):
        parse_and_validate_cast_proposal(too_many)


def test_missing_protagonist_marker_is_auto_labeled_not_rejected() -> None:
    """A real model's wording won't always match `_PROTAGONIST_ROLE_MARKERS`.

    Downstream code already treats the *first* character positionally as the
    protagonist regardless of role text, so a wording mismatch should not
    lose an otherwise-valid proposal — it should just get an accurate,
    visible label prefixed onto it. This replaced a fail-closed behavior
    that a live OpenAI call actually hit in production: the model wrote a
    role that didn't contain any of the (too-narrow) marker strings, and the
    whole cast proposal was rejected outright.
    """

    no_marker = (
        '[{"name": "Mira", "role": "Guild Enforcer", "voice": "", "traits": "", "visual": ""},'
        '{"name": "Dial", "role": "Sentient Artifact", "voice": "", "traits": "", "visual": ""}]'
    )
    characters = parse_and_validate_cast_proposal(no_marker)
    assert characters[0].role == "Protagonist · Guild Enforcer"
    assert characters[1].role == "Sentient Artifact"


def test_hindi_protagonist_role_is_accepted() -> None:
    hindi_cast = (
        '[{"name": "आप", "role": "मुख्य पात्र · चंद्र अन्वेषक", "voice": "सीधी", '
        '"traits": "जिज्ञासु", "visual": "अंतरिक्ष सूट"},'
        '{"name": "राहुल", "role": "साथी", "voice": "सहायक", '
        '"traits": "वफादार", "visual": "अंतरिक्ष सूट"}]'
    )

    characters = parse_and_validate_cast_proposal(hindi_cast)

    assert characters[0].name == "आप"


def test_a_stray_hidden_field_from_the_model_is_dropped_not_rejected() -> None:
    # Defensive-in-depth: even if the model invents a "hidden" field (the
    # exact prototype pattern task.md 0.4 says not to port), the parser
    # drops unknown keys rather than either crashing or silently trusting
    # them into the returned character.
    with_stray_field = (
        '[{"name": "Kaelen", "role": "Protagonist", "voice": "", "traits": "", '
        '"visual": "", "hidden": "a dark secret"}]'
    )
    characters = parse_and_validate_cast_proposal(with_stray_field)
    assert len(characters) == 1
    assert not hasattr(characters[0], "hidden")


def test_non_object_array_element_fails_closed() -> None:
    with pytest.raises(CastProposalError):
        parse_and_validate_cast_proposal('["not an object", "also not"]')


def test_missing_required_field_fails_closed() -> None:
    missing_name = '[{"role": "Protagonist", "voice": "", "traits": "", "visual": ""}]'
    with pytest.raises(CastProposalError):
        parse_and_validate_cast_proposal(missing_name)


def test_seed_fallback_preserves_named_companions_and_setting() -> None:
    characters = fallback_cast_from_seed("i am on moon with my 2 friends rahul and teja")

    assert [character.name for character in characters] == ["You", "Rahul", "Teja"]
    assert characters[0].role == "Protagonist · Lunar explorer"
