"""Typed policy decisions shared by API, agent, and template boundaries."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PolicySubject(StrEnum):
    SEED = "seed"
    CLARIFICATION = "clarification"
    TEMPLATE = "template"
    TRAIT_EDIT = "trait_edit"
    CANON_EVENT = "canon_event"
    CANDIDATE_PROSE = "candidate_prose"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    REDIRECT = "redirect"
    BLOCK = "block"


class PolicyCategory(StrEnum):
    GRAPHIC_VIOLENCE = "graphic_violence"
    SEXUAL_CONTENT = "sexual_content"
    MINOR_SEXUALIZATION = "minor_sexualization"
    HATE_OR_EXTREMISM = "hate_or_extremism"
    SELF_HARM_GLORIFICATION = "self_harm_glorification"
    REAL_PERSON_PRIVACY = "real_person_privacy"
    UNLICENSED_IP = "unlicensed_ip"
    DISTRESS = "distress"
    TRAIT_ESCALATION = "trait_escalation"


class PolicyResult(BaseModel):
    """A user-facing decision without exposing provider internals."""

    model_config = ConfigDict(frozen=True)

    decision: PolicyDecision
    category: PolicyCategory | None = None
    message: str = Field(min_length=1, max_length=500)
    safe_alternative: str | None = Field(default=None, max_length=500)

