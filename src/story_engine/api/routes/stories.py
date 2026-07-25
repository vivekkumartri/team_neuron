"""Story REST endpoints with RLS-scoped queries."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection

router = APIRouter(prefix="/api/v1/stories", tags=["stories"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class StoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    personalization_enabled: bool = False
    agent_trace_enabled: bool = False


class StoryResponse(BaseModel):
    id: UUID
    title: str
    personalization_enabled: bool
    agent_trace_enabled: bool
    initial_branch_id: UUID | None = None
    initial_focal_entity_id: UUID | None = None


def _story_response(row: object) -> StoryResponse:
    values = cast(tuple[object, ...], row)
    return StoryResponse(
        id=UUID(str(values[0])),
        title=str(values[1]),
        personalization_enabled=bool(values[2]),
        agent_trace_enabled=bool(values[3]),
        initial_branch_id=(
            UUID(str(values[4])) if len(values) > 4 and values[4] is not None else None
        ),
        initial_focal_entity_id=(
            UUID(str(values[5])) if len(values) > 5 and values[5] is not None else None
        ),
    )


@router.get("", response_model=list[StoryResponse])
def list_stories(user: CurrentUser) -> list[StoryResponse]:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT s.id, s.title, s.personalization_enabled, s.agent_trace_enabled, "
                "(SELECT b.id FROM branches b WHERE b.story_id=s.id AND b.archived_at IS NULL "
                " ORDER BY b.created_at LIMIT 1), "
                "(SELECT e.id FROM entities e WHERE e.story_id=s.id AND e.entity_type='character' "
                " ORDER BY e.created_at LIMIT 1) "
                "FROM stories s WHERE s.deleted_at IS NULL ORDER BY s.created_at DESC"
            )
            rows = cursor.fetchall()
    return [_story_response(row) for row in rows]


@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
def create_story(payload: StoryInput, user: CurrentUser) -> StoryResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO stories (user_id, title, personalization_enabled, "
                "agent_trace_enabled) "
                "VALUES (%s, %s, %s, %s) "
                "RETURNING id, title, personalization_enabled, agent_trace_enabled",
                (
                    user.id,
                    payload.title,
                    payload.personalization_enabled,
                    payload.agent_trace_enabled,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Story creation failed"
                )
            values = cast(tuple[object, ...], row)
            story_id = UUID(str(values[0]))
            cursor.execute(
                "INSERT INTO arcs (story_id, name) VALUES (%s, 'Main arc') RETURNING id",
                (story_id,),
            )
            arc_id = UUID(str(cast(tuple[object, ...], cursor.fetchone())[0]))
            cursor.execute(
                "INSERT INTO branches (story_id, arc_id, name, status) "
                "VALUES (%s, %s, 'Main timeline', 'ACTIVE') RETURNING id",
                (story_id, arc_id),
            )
            branch_id = UUID(str(cast(tuple[object, ...], cursor.fetchone())[0]))
            cursor.execute(
                "INSERT INTO entities (story_id, name, entity_type, founding_branch_id) "
                "VALUES (%s, 'Protagonist', 'character', %s) RETURNING id",
                (story_id, branch_id),
            )
            focal_id = UUID(str(cast(tuple[object, ...], cursor.fetchone())[0]))
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Story creation failed"
        )
    return StoryResponse(
        id=story_id,
        title=str(values[1]),
        personalization_enabled=bool(values[2]),
        agent_trace_enabled=bool(values[3]),
        initial_branch_id=branch_id,
        initial_focal_entity_id=focal_id,
    )
