"""Task 5J.1: disclosed-template/IP and sensitive-content handling checks.

The canon-event type space is a closed enum (never free text), which is
itself a policy guard — an author or a compromised client can never request
an arbitrary, undefined canon-event category. The frontend template picker
is checked for explicit licensed-reference disclosure via a source scan,
mirroring the same technique already used for the retired hidden-row/blur
patterns (see `web/components/features/onboarding/TemplatePicker.tsx`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from story_engine.domain.policy_models import PolicyCategory, PolicyDecision
from story_engine.security.content_policy import RuleBasedContentPolicy
from story_engine.security.director_memory_policy import DirectorMemoryRecord
from story_engine.services.canon_events import CanonEventType

REPO_ROOT = Path(__file__).resolve().parents[2]

_POLICY = RuleBasedContentPolicy()


@pytest.mark.parametrize(
    ("text", "expected_category"),
    [
        ("a minor child having sex with an adult", PolicyCategory.MINOR_SEXUALIZATION),
        ("a story that would glorify suicide as heroic", PolicyCategory.SELF_HARM_GLORIFICATION),
        ("graphic torture and dismemberment scene", PolicyCategory.GRAPHIC_VIOLENCE),
        ("an explicit sex scene between two characters", PolicyCategory.SEXUAL_CONTENT),
        ("praise the nazi party's ideology", PolicyCategory.HATE_OR_EXTREMISM),
        ("a deepfake of a recognizable private person", PolicyCategory.REAL_PERSON_PRIVACY),
        ("write a scene starring Harry Potter", PolicyCategory.UNLICENSED_IP),
    ],
)
def test_every_blocked_safety_category_is_actually_blocked(
    text: str, expected_category: PolicyCategory
) -> None:
    """Adversarial coverage for every `PolicyCategory` the baseline gate blocks.

    Task 2D.4 built `RuleBasedContentPolicy`/`PolicyCategory` and unit-tested
    it from a correctness angle (`tests/unit/domain/test_content_policy.py`).
    This is the security-suite's adversarial angle: prove each prohibited
    category from `requirements.md` is fail-closed (BLOCK, not ALLOW), with a
    concrete safe alternative offered rather than a bare rejection.
    """

    result = _POLICY.assess(text, subject=object())  # type: ignore[arg-type]
    assert result.decision == PolicyDecision.BLOCK
    assert result.category == expected_category
    assert result.safe_alternative, "a blocked category must always offer a safe alternative"


def test_distress_input_redirects_rather_than_blocks_or_generates() -> None:
    result = _POLICY.assess("i want to kill myself tonight", subject=object())  # type: ignore[arg-type]
    assert result.decision == PolicyDecision.REDIRECT
    assert result.category == PolicyCategory.DISTRESS
    assert "support" in result.safe_alternative.lower()


def test_director_memory_rejects_an_attempt_to_smuggle_private_character_data() -> None:
    """Adversarial angle on Task 2D.3's Director-memory safeguard.

    `tests/integration/persistence/test_memory_cutoffs.py` covers the DB-level
    cutoff mechanism; this proves the pure validation layer itself refuses to
    construct a `DirectorMemoryRecord` carrying a hidden characteristic or a
    character's private memory excerpt, independent of any database access.
    """

    from uuid import uuid4

    # Pydantic wraps the validator's `UnsafeDirectorMemory` (a `ValueError`
    # subclass) into its own `ValidationError`; the underlying message is
    # still surfaced, so we assert on that rather than the wrapped type.
    with pytest.raises(ValidationError, match="Director memory cannot contain private character data"):
        DirectorMemoryRecord(
            branch_id=uuid4(),
            summary="The character's hidden characteristic is that they secretly plan betrayal.",
        )


def test_canon_event_type_is_a_closed_enum_not_free_text() -> None:
    # Enforced structurally: `CanonEventType` is a `StrEnum`, so any value
    # outside its five members fails Pydantic validation before it ever
    # reaches a database write or an agent.
    assert set(CanonEventType) == {
        CanonEventType.KILL,
        CanonEventType.REVIVE,
        CanonEventType.MOVE_REALM,
        CanonEventType.INTRODUCE_ENTITY,
        CanonEventType.EDIT_CANON,
    }


def test_template_picker_discloses_licensed_reference_templates() -> None:
    source = (REPO_ROOT / "web/components/features/onboarding/TemplatePicker.tsx").read_text()
    assert "LICENSED_REFERENCE" in source
    assert "Licensed reference" in source, "the disclosure label must be visible copy, not just a code value"


def test_no_template_is_silently_presented_as_original_when_licensed() -> None:
    source = (REPO_ROOT / "web/components/features/onboarding/TemplatePicker.tsx").read_text()
    template_array_source = source.split("const TEMPLATES", 1)[1]
    # Every template literal in the array must declare a disclosure — a
    # crude but effective guard against someone adding a new template object
    # without the `disclosure` field.
    assert template_array_source.count('id: "') == template_array_source.count('disclosure: "')
