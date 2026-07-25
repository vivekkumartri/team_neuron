"""User personalization preferences and immutable snapshot endpoints.

Matches design.md's API contract: preferences are private to the user, never
story canon, and only an explicitly approved snapshot is eligible for a
generation job (design.md "Security and Data Boundaries").
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection

router = APIRouter(prefix="/api/v1/me", tags=["preferences"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]

ALLOWED_CATEGORIES = {"CREATIVE", "INTERACTION", "ACCESSIBILITY", "CONTENT_BOUNDARY"}


class PreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preference_key: str = Field(min_length=1, max_length=100)
    preference_value: Any
    source: str = Field(default="EXPLICIT", pattern="^(EXPLICIT|INFERRED)$")


class PreferenceResponse(BaseModel):
    id: UUID
    preference_key: str
    preference_value: Any
    source: str
    consented_at: str
    revoked_at: str | None


class SnapshotResponse(BaseModel):
    id: UUID
    snapshot_version: int


def _preference_response(row: tuple[Any, ...]) -> PreferenceResponse:
    return PreferenceResponse(
        id=UUID(str(row[0])),
        preference_key=str(row[1]),
        preference_value=row[2],
        source=str(row[3]),
        consented_at=str(row[4]),
        revoked_at=str(row[5]) if row[5] is not None else None,
    )


@router.get("/preferences", response_model=list[PreferenceResponse])
def list_preferences(user: CurrentUser) -> list[PreferenceResponse]:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, preference_key, preference_value, source, consented_at, revoked_at "
                "FROM user_preferences WHERE user_id = %s AND revoked_at IS NULL "
                "ORDER BY preference_key",
                (user.id,),
            )
            rows = cursor.fetchall()
    return [_preference_response(cast(tuple[Any, ...], row)) for row in rows]


@router.patch("/preferences", response_model=PreferenceResponse)
def upsert_preference(payload: PreferenceInput, user: CurrentUser) -> PreferenceResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO user_preferences "
                "(user_id, preference_key, preference_value, source, consented_at) "
                "VALUES (%s, %s, %s, %s, now()) "
                "ON CONFLICT (user_id, preference_key) DO UPDATE SET "
                "  preference_value = EXCLUDED.preference_value, "
                "  source = EXCLUDED.source, "
                "  consented_at = now(), "
                "  revoked_at = NULL "
                "RETURNING id, preference_key, preference_value, source, consented_at, revoked_at",
                (user.id, payload.preference_key, payload.preference_value, payload.source),
            )
            row = cursor.fetchone()
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Preference save failed"
        )
    return _preference_response(cast(tuple[Any, ...], row))


@router.delete("/preferences/{preference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preference(preference_id: UUID, user: CurrentUser) -> None:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE user_preferences SET revoked_at = now() "
                "WHERE id = %s AND user_id = %s AND revoked_at IS NULL",
                (preference_id, user.id),
            )
            affected = cursor.rowcount
        connection.commit()
    if affected == 0:
        # RLS already hides other users' rows; 404 here also covers "already deleted".
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preference not found")


@router.post(
    "/personalization-snapshots",
    response_model=SnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_personalization_snapshot(user: CurrentUser) -> SnapshotResponse:
    """Freeze the caller's current consented preferences into an immutable, versioned snapshot."""

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT preference_key, preference_value FROM user_preferences "
                "WHERE user_id = %s AND revoked_at IS NULL",
                (user.id,),
            )
            preference_rows = cast(list[tuple[Any, ...]], cursor.fetchall())
            preferences = {key: value for key, value in preference_rows}

            cursor.execute(
                "SELECT COALESCE(MAX(snapshot_version), 0) + 1 FROM personalization_snapshots "
                "WHERE user_id = %s",
                (user.id,),
            )
            version_row = cast(tuple[Any, ...], cursor.fetchone())
            next_version = version_row[0]

            cursor.execute(
                "INSERT INTO personalization_snapshots (user_id, snapshot_version, preferences) "
                "VALUES (%s, %s, %s) RETURNING id, snapshot_version",
                (user.id, next_version, preferences),
            )
            row = cursor.fetchone()
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Snapshot creation failed"
        )
    values = cast(tuple[Any, ...], row)
    return SnapshotResponse(id=UUID(str(values[0])), snapshot_version=int(values[1]))
