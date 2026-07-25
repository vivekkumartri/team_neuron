"""Replaceable policy gate for story inputs and generated text.

This deterministic baseline is deliberately conservative and is not a substitute for
the configured moderation provider required before a public production launch.
"""

from __future__ import annotations

import re
from typing import Protocol

from story_engine.domain.policy_models import (
    PolicyCategory,
    PolicyDecision,
    PolicyResult,
    PolicySubject,
)


class ModerationAdapter(Protocol):
    """Provider seam; implementations return a typed local policy result."""

    def assess(self, text: str, subject: PolicySubject) -> PolicyResult: ...


_RULES: tuple[tuple[PolicyCategory, re.Pattern[str]], ...] = (
    (
        PolicyCategory.MINOR_SEXUALIZATION,
        re.compile(r"\b(?:minor|child|underage).{0,40}\b(?:sex|nude)", re.I),
    ),
    (
        PolicyCategory.SELF_HARM_GLORIFICATION,
        re.compile(r"\b(?:glorif(?:y|ies|ied)|celebrate).{0,40}\b(?:suicide|self-harm)", re.I),
    ),
    (
        PolicyCategory.GRAPHIC_VIOLENCE,
        re.compile(r"\b(?:gore|dismember(?:ed|ment)?|graphic torture)\b", re.I),
    ),
    (
        PolicyCategory.SEXUAL_CONTENT,
        re.compile(r"\b(?:explicit sex|pornographic|erotic nude)\b", re.I),
    ),
    (
        PolicyCategory.HATE_OR_EXTREMISM,
        re.compile(
            r"\b(?:praise|recruit for).{0,40}\b(?:nazi|white supremac(?:y|ist)|terrorist group)\b",
            re.I,
        ),
    ),
    (
        PolicyCategory.REAL_PERSON_PRIVACY,
        re.compile(r"\b(?:deepfake|recognizable).{0,50}\b(?:private person|real person)\b", re.I),
    ),
    (
        PolicyCategory.UNLICENSED_IP,
        re.compile(r"\b(?:harry potter|hermione granger|darth vader|mickey mouse)\b", re.I),
    ),
)
_DISTRESS = re.compile(
    r"\b(?:i want to (?:die|kill myself)|suicidal|self harm tonight)\b", re.I
)
_TRAIT_SPIRAL = re.compile(
    r"\b(?:make|become).{0,40}\b(?:more violent|crueller|more abusive)\b", re.I
)


class RuleBasedContentPolicy:
    """Baseline policy adapter with clear safe alternatives."""

    def assess(self, text: str, subject: PolicySubject) -> PolicyResult:
        del subject  # Every current subject has the same baseline restrictions.
        if _DISTRESS.search(text):
            return PolicyResult(
                decision=PolicyDecision.REDIRECT,
                category=PolicyCategory.DISTRESS,
                message="This sounds personal and urgent, so we cannot turn it into entertainment.",
                safe_alternative=(
                    "Consider contacting local emergency support or someone you trust now."
                ),
            )
        if _TRAIT_SPIRAL.search(text):
            return PolicyResult(
                decision=PolicyDecision.REDIRECT,
                category=PolicyCategory.TRAIT_ESCALATION,
                message="That change risks an escalating harmful-trait pattern.",
                safe_alternative="Try a conflict, setback, or accountable growth arc instead.",
            )
        for category, pattern in _RULES:
            if pattern.search(text):
                return PolicyResult(
                    decision=PolicyDecision.BLOCK,
                    category=category,
                    message="This request is not supported for this story experience.",
                    safe_alternative=_safe_alternative(category),
                )
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            message="Content passed the baseline policy gate.",
        )


def _safe_alternative(category: PolicyCategory) -> str:
    alternatives = {
        PolicyCategory.GRAPHIC_VIOLENCE: "Use non-graphic danger and its emotional consequences.",
        PolicyCategory.SEXUAL_CONTENT: "Use a consensual, non-explicit relationship moment.",
        PolicyCategory.MINOR_SEXUALIZATION: (
            "Keep all characters age-appropriate and remove sexual content."
        ),
        PolicyCategory.HATE_OR_EXTREMISM: (
            "Explore conflict without endorsing hate or extremist recruitment."
        ),
        PolicyCategory.SELF_HARM_GLORIFICATION: (
            "Focus on support, recovery, or a non-self-harm conflict."
        ),
        PolicyCategory.REAL_PERSON_PRIVACY: (
            "Create a fictional character who is not recognizable as a private person."
        ),
        PolicyCategory.UNLICENSED_IP: (
            "Use an original alternate archetype rather than a named protected character."
        ),
    }
    return alternatives[category]


def quota_message(*, limit: int, retry_after_seconds: int | None = None) -> str:
    """Keep quota feedback explicit at every client boundary."""

    retry_hint = f" Try again in {retry_after_seconds} seconds." if retry_after_seconds else ""
    return f"Generation limit reached ({limit}). No story content was changed.{retry_hint}"
