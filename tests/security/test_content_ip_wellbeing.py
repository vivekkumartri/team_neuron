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

from story_engine.services.canon_events import CanonEventType

REPO_ROOT = Path(__file__).resolve().parents[2]


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
