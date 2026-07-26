"""Read-only branch-scoped world state, plus canon-event *requests*.

Submitting a request only ever creates a `DRAFT` row here — evaluator review
and the world-agent's final commit/adjust/reject decision (via
`world_commit_canon_event`, migration 0009) are Track E/worker concerns, not
something this route performs itself.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from psycopg.types.json import Jsonb
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


def _etag_for(payload: BaseModel) -> str:
    """A weak content hash, not a version counter — good enough to detect

    "did this branch's state change out from under me" between a client's
    read and its next write, per design.md's stale-write guard, without
    needing a dedicated version column on every read path.
    """

    digest = hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()
    return f'W/"{digest[:32]}"'


def _fetch_branch_state(connection: Any, branch_id: UUID) -> BranchStateResponse:
    """Shared by the GET read path and the If-Match precondition check on

    writes below, so the ETag a client received from `GET .../state` is
    always computed the exact same way it's later recomputed for comparison.
    """

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


def _check_if_match(connection: Any, branch_id: UUID, if_match: str | None) -> None:
    """Optimistic-concurrency guard for branch-scoped writes.

    If the client didn't send `If-Match`, the write proceeds unconditionally
    (the header is opt-in, matching how `GET .../state`'s ETag is advertised
    rather than mandated). If it did send one, recompute the current state's
    ETag inside the same transaction the write will use and reject with 412
    on any mismatch — including the wildcard `*`, which this route treats as
    "state must still exist" rather than "always match".
    """

    if if_match is None:
        return
    current = _fetch_branch_state(connection, branch_id)
    current_etag = _etag_for(current)
    candidates = {tag.strip() for tag in if_match.split(",")}
    if "*" in candidates:
        return
    if current_etag not in candidates:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Branch state has changed since the If-Match ETag was read; "
            "re-fetch GET /branches/{branch_id}/state and retry.",
        )


@router.get("/{branch_id}/state", response_model=BranchStateResponse)
def get_branch_state(
    branch_id: UUID, user: CurrentUser, response: Response
) -> BranchStateResponse:
    with tenant_connection(user) as connection:
        result = _fetch_branch_state(connection, branch_id)
    response.headers["ETag"] = _etag_for(result)
    return result


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
    branch_id: UUID,
    payload: CanonEventRequestInput,
    user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> CanonEventRequestResponse:
    if requires_target_entity(payload.event_type) and payload.target_entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{payload.event_type} requires target_entity_id",
        )

    with tenant_connection(user) as connection:
        _check_if_match(connection, branch_id, if_match)
        with connection.cursor() as cursor:
            if idempotency_key is not None:
                cursor.execute(
                    "SELECT id, status FROM canon_event_requests "
                    "WHERE requested_by_user_id = %s AND idempotency_key = %s",
                    (user.id, idempotency_key),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    values = cast(tuple[Any, ...], existing)
                    return CanonEventRequestResponse(id=UUID(str(values[0])), status=str(values[1]))

            cursor.execute(
                "INSERT INTO canon_event_requests "
                "(branch_id, requested_by_user_id, event_type, target_entity_id, "
                " proposed_payload, rationale, status, idempotency_key) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'DRAFT', %s) RETURNING id, status",
                (
                    branch_id,
                    user.id,
                    payload.event_type.value,
                    payload.target_entity_id,
                    Jsonb(payload.proposed_payload),
                    payload.rationale,
                    idempotency_key,
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
