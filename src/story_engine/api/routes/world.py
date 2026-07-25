"""Read-only branch-scoped world state, plus canon-event *requests*.

Submitting a request only ever creates a `DRAFT` row here — evaluator review
and the world-agent's final commit/adjust/reject decision (via
`world_commit_canon_event`, migration 0009) are Track E/worker concerns, not
something this route performs itself.
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.services.canon_events import CanonEventType, requires_target_entity

router = APIRouter(prefix="/api/v1/branches", tags=["world"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class EntityState(BaseModel):
    entity_id: UUID
    name: str
    entity_type: str
    location_entity_id: UUID | None
    state: dict[str, Any]


class Relationship(BaseModel):
    from_entity_id: UUID
    to_entity_id: UUID
    relationship_type: str


class BranchStateResponse(BaseModel):
    branch_id: UUID
    entities: list[EntityState]
    relationships: list[Relationship]


@router.get("/{branch_id}/state", response_model=BranchStateResponse)
def get_branch_state(branch_id: UUID, user: CurrentUser) -> BranchStateResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT e.id, e.name, e.entity_type, bes.location_entity_id, bes.state "
                "FROM branch_entity_states bes "
                "JOIN entities e ON e.id = bes.entity_id "
                "WHERE bes.branch_id = %s AND bes.is_current",
                (branch_id,),
            )
            entity_rows = cast(list[tuple[Any, ...]], cursor.fetchall())

            cursor.execute(
                "SELECT from_entity_id, to_entity_id, relationship_type FROM branch_relationships "
                "WHERE branch_id = %s "
                "ORDER BY version DESC",
                (branch_id,),
            )
            relationship_rows = cast(list[tuple[Any, ...]], cursor.fetchall())

    return BranchStateResponse(
        branch_id=branch_id,
        entities=[
            EntityState(
                entity_id=UUID(str(eid)),
                name=str(name),
                entity_type=str(etype),
                location_entity_id=UUID(str(loc)) if loc is not None else None,
                state=cast(dict[str, Any], state),
            )
            for eid, name, etype, loc, state in entity_rows
        ],
        relationships=[
            Relationship(
                from_entity_id=UUID(str(fr)), to_entity_id=UUID(str(to)), relationship_type=str(rt)
            )
            for fr, to, rt in relationship_rows
        ],
    )


class CanonEventRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: CanonEventType
    target_entity_id: UUID | None = None
    proposed_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = Field(default=None, max_length=2_000)


class CanonEventRequestResponse(BaseModel):
    id: UUID
    status: str


@router.post(
    "/{branch_id}/canon-event-requests",
    response_model=CanonEventRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_canon_event_request(
    branch_id: UUID, payload: CanonEventRequestInput, user: CurrentUser
) -> CanonEventRequestResponse:
    if requires_target_entity(payload.event_type) and payload.target_entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{payload.event_type} requires target_entity_id",
        )

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO canon_event_requests "
                "(branch_id, requested_by_user_id, event_type, target_entity_id, "
                " proposed_payload, rationale, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'DRAFT') RETURNING id, status",
                (
                    branch_id,
                    user.id,
                    payload.event_type.value,
                    payload.target_entity_id,
                    payload.proposed_payload,
                    payload.rationale,
                ),
            )
            row = cursor.fetchone()
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Request creation failed"
        )
    values = cast(tuple[Any, ...], row)
    return CanonEventRequestResponse(id=UUID(str(values[0])), status=str(values[1]))
