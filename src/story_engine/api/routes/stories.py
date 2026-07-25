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


def _story_response(row: object) -> StoryResponse:
    values = cast(tuple[object, object, object, object], row)
    return StoryResponse(
        id=UUID(str(values[0])),
        title=str(values[1]),
        personalization_enabled=bool(values[2]),
        agent_trace_enabled=bool(values[3]),
    )


@router.get("", response_model=list[StoryResponse])
def list_stories(user: CurrentUser) -> list[StoryResponse]:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, personalization_enabled, agent_trace_enabled "
                "FROM stories WHERE deleted_at IS NULL ORDER BY created_at DESC"
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
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Story creation failed"
        )
    return _story_response(row)
