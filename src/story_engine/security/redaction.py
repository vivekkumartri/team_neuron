"""Reject unsafe data before it is formatted as a client-visible event."""

from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import UUID

from story_engine.domain.events import ClientGenerationEvent, PublicAgentLabel
from story_engine.domain.models import ChapterStatus


class UnsafeClientEvent(ValueError):
    """Raised when an event would disclose data outside the public allowlist."""


_CREDENTIAL_PATTERNS = (
    re.compile(r"\b(?:sk|pk|api)[_-][A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\b(?:authorization|bearer)\s*[:=]", re.IGNORECASE),
    re.compile(r"\b(?:password|secret|token)\s*[:=]", re.IGNORECASE),
)
_RAW_INTERNAL_PATTERNS = (
    re.compile(r"\b(?:system prompt|developer message|tool call)\b", re.IGNORECASE),
    re.compile(r"\b(?:chain[ -]of[ -]thought|internal reasoning)\b", re.IGNORECASE),
)


def _contains_any(text: str, values: Iterable[str | UUID]) -> bool:
    folded = text.casefold()
    return any(str(value).casefold() in folded for value in values if str(value))


def assert_public_text(
    text: str,
    *,
    unrevealed_values: Iterable[str] = (),
    foreign_tenant_identifiers: Iterable[str | UUID] = (),
    known_secrets: Iterable[str] = (),
) -> None:
    """Reject, rather than silently leak, non-public data in a text field."""

    if _contains_any(text, unrevealed_values):
        raise UnsafeClientEvent("Event contains an unrevealed hidden characteristic")
    if _contains_any(text, foreign_tenant_identifiers):
        raise UnsafeClientEvent("Event contains a cross-tenant identifier")
    if _contains_any(text, known_secrets):
        raise UnsafeClientEvent("Event contains a known secret")
    if any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS):
        raise UnsafeClientEvent("Event contains credential-like material")
    if any(pattern.search(text) for pattern in _RAW_INTERNAL_PATTERNS):
        raise UnsafeClientEvent("Event contains raw internal agent material")


def build_client_event(
    *,
    sequence: int,
    summary: str,
    agent: PublicAgentLabel,
    status: ChapterStatus,
    entity_id: UUID | None = None,
    unrevealed_values: Iterable[str] = (),
    foreign_tenant_identifiers: Iterable[str | UUID] = (),
    known_secrets: Iterable[str] = (),
) -> ClientGenerationEvent:
    """Validate allowed fields and create the only client-facing event type."""

    assert_public_text(
        summary,
        unrevealed_values=unrevealed_values,
        foreign_tenant_identifiers=foreign_tenant_identifiers,
        known_secrets=known_secrets,
    )
    return ClientGenerationEvent(
        sequence=sequence,
        summary=summary,
        agent=agent,
        status=status,
        entity_id=entity_id,
    )

