"""Structured boundaries for untrusted text and agent proposals."""

from __future__ import annotations

import html
import re
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UnsafePromptInput(ValueError):
    """Raised when untrusted text asks to override system authority."""


class ProposalAction(StrEnum):
    SUGGEST_SCENE = "suggest_scene"
    FLAG_CONTINUITY = "flag_continuity"
    REQUEST_REVIEW = "request_review"


_AUTHORITY_BYPASS = re.compile(
    r"\b(?:ignore|override|bypass)\b.{0,80}\b(?:instructions?|policy|guardrails?)\b"
    r"|\b(?:reveal|exfiltrate|show)\b.{0,80}\b(?:secret|system prompt|credential)\b"
    r"|\b(?:write|commit|publish)\b.{0,80}\b(?:canon|database|production)\b",
    re.IGNORECASE,
)


class AgentProposal(BaseModel):
    """A non-privileged, validated output from an agent adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: ProposalAction
    chapter_id: UUID
    rationale: str = Field(min_length=1, max_length=1_000)
    proposed_text: str | None = Field(default=None, max_length=5_000)

    @field_validator("rationale", "proposed_text")
    @classmethod
    def reject_authority_language(cls, value: str | None) -> str | None:
        if value and _AUTHORITY_BYPASS.search(value):
            raise ValueError("Proposal includes a privileged instruction or canonical write")
        return value


def delimit_untrusted_text(value: str, *, source: str) -> str:
    """Render user/generated text as inert data for a structured prompt.

    The caller must keep this block separate from system instructions and tool schema.
    """

    if not value.strip():
        raise UnsafePromptInput("Untrusted input cannot be empty")
    if _AUTHORITY_BYPASS.search(value):
        raise UnsafePromptInput("Untrusted input requests a forbidden authority action")
    escaped = html.escape(value, quote=False)
    return f"<untrusted-data source=\"{source}\">{escaped}</untrusted-data>"

