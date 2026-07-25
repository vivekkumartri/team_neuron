"""Canon-event request lifecycle: evaluator-advisory, world-agent-final.

Matches design.md: "The evaluator is an advisory validation input for author
requests; the world agent remains the final authority for canon writes."
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from story_engine.domain.models import CanonEventStatus


class CanonEventType(StrEnum):
    KILL = "KILL"
    REVIVE = "REVIVE"
    MOVE_REALM = "MOVE_REALM"
    INTRODUCE_ENTITY = "INTRODUCE_ENTITY"
    EDIT_CANON = "EDIT_CANON"


class CanonEventRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    branch_id: UUID
    event_type: CanonEventType
    target_entity_id: UUID | None = None
    proposed_payload: dict[str, object] = Field(default_factory=dict)
    rationale: str | None = Field(default=None, max_length=2_000)
    status: CanonEventStatus = CanonEventStatus.DRAFT


class CanonEventTransitionError(ValueError):
    """An illegal canon-event status transition was attempted."""


_ALLOWED_TRANSITIONS: dict[CanonEventStatus, frozenset[CanonEventStatus]] = {
    CanonEventStatus.DRAFT: frozenset({CanonEventStatus.EVALUATING}),
    CanonEventStatus.EVALUATING: frozenset(
        {
            CanonEventStatus.APPROVED,
            CanonEventStatus.ADJUSTED,
            CanonEventStatus.REJECTED,
            CanonEventStatus.FAILED,
        }
    ),
    CanonEventStatus.APPROVED: frozenset(),
    CanonEventStatus.ADJUSTED: frozenset(),
    CanonEventStatus.REJECTED: frozenset({CanonEventStatus.DRAFT}),  # may be revised/resubmitted
    CanonEventStatus.FAILED: frozenset({CanonEventStatus.DRAFT}),
}


def ensure_canon_event_transition(current: CanonEventStatus, target: CanonEventStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise CanonEventTransitionError(
            f"Cannot move a canon event request from {current} to {target}"
        )


def requires_target_entity(event_type: CanonEventType) -> bool:
    return event_type in {CanonEventType.KILL, CanonEventType.REVIVE, CanonEventType.MOVE_REALM}


class SuggestedRelationship(BaseModel):
    """A world-agent-suggested link to an existing entity, offered for author
    confirmation before evaluation — closes the FR-3.2 requirement that a
    newly introduced character is folded into the roster with suggested
    relationships rather than left disconnected.
    """

    model_config = ConfigDict(frozen=True)

    to_entity_id: UUID
    relationship_type: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)


def build_introduce_entity_request(
    *,
    branch_id: UUID,
    proposed_payload: dict[str, object],
    suggested_relationships: list[SuggestedRelationship],
    rationale: str | None = None,
) -> CanonEventRequest:
    """INTRODUCE_ENTITY requests carry suggested relationships in the payload
    for the author to confirm; they are proposals, never auto-committed.
    """

    payload = dict(proposed_payload)
    payload["suggested_relationships"] = [
        relationship.model_dump(mode="json") for relationship in suggested_relationships
    ]
    return CanonEventRequest(
        branch_id=branch_id,
        event_type=CanonEventType.INTRODUCE_ENTITY,
        proposed_payload=payload,
        rationale=rationale,
    )
