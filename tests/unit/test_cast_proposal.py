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


def test_missing_protagonist_role_fails_closed() -> None:
    no_protagonist = (
        '[{"name": "Mira", "role": "Guild Enforcer", "voice": "", "traits": "", "visual": ""},'
        '{"name": "Dial", "role": "Sentient Artifact", "voice": "", "traits": "", "visual": ""}]'
    )
    with pytest.raises(CastProposalError):
        parse_and_validate_cast_proposal(no_protagonist)


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
