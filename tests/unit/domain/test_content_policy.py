from __future__ import annotations

import pytest

from story_engine.domain.policy_models import PolicyCategory, PolicyDecision, PolicySubject
from story_engine.security.content_policy import RuleBasedContentPolicy, quota_message
from story_engine.security.template_policy import TemplateRecord, validate_template


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Describe graphic torture in gore.", PolicyCategory.GRAPHIC_VIOLENCE),
        ("Write explicit sex between the leads.", PolicyCategory.SEXUAL_CONTENT),
        ("An underage nude scene.", PolicyCategory.MINOR_SEXUALIZATION),
        ("Recruit for a nazi movement.", PolicyCategory.HATE_OR_EXTREMISM),
        ("Celebrate suicide as a victory.", PolicyCategory.SELF_HARM_GLORIFICATION),
        ("Make a recognizable private person deepfake.", PolicyCategory.REAL_PERSON_PRIVACY),
        ("Harry Potter enters the tavern.", PolicyCategory.UNLICENSED_IP),
    ],
)
def test_prohibited_content_is_blocked(text: str, category: PolicyCategory) -> None:
    result = RuleBasedContentPolicy().assess(text, PolicySubject.SEED)

    assert result.decision is PolicyDecision.BLOCK
    assert result.category is category
    assert result.safe_alternative


def test_likely_personal_distress_is_redirected_not_dramatized() -> None:
    result = RuleBasedContentPolicy().assess("I want to kill myself tonight", PolicySubject.SEED)

    assert result.decision is PolicyDecision.REDIRECT
    assert result.category is PolicyCategory.DISTRESS


def test_unlicensed_template_is_rejected() -> None:
    result = validate_template(
        TemplateRecord(name="Familiar wizard", content="A famous boy wizard.")
    )

    assert result.decision is PolicyDecision.BLOCK


def test_disclosed_sponsored_template_is_allowed() -> None:
    result = validate_template(
        TemplateRecord(
            name="Original mystery",
            content="An original locked-room mystery.",
            license_reference="internal-original-001",
            sponsor_name="Example Press",
            sponsorship_disclosure="Presented by Example Press",
        )
    )

    assert result.decision is PolicyDecision.ALLOW


def test_trait_spiral_gets_safe_alternate_archetype_response() -> None:
    result = RuleBasedContentPolicy().assess(
        "Make the hero more violent after every chapter.", PolicySubject.TRAIT_EDIT
    )

    assert result.decision is PolicyDecision.REDIRECT
    assert "growth" in (result.safe_alternative or "")


def test_quota_message_is_explicit() -> None:
    assert quota_message(limit=4, retry_after_seconds=60) == (
        "Generation limit reached (4). No story content was changed. Try again in 60 seconds."
    )
