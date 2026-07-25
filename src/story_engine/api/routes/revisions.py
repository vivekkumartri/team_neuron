"""Chapter revision requests: always a DRAFT row here; approval and the
replacement-branch creation it requires happen out of band (evaluator +
world agent), per `services/revisions.py`'s "approved implies replacement
branch" invariant. This route never edits a published chapter in place.
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.api.routes.world import _check_if_match

router = APIRouter(prefix="/api/v1/chapters", tags=["revisions"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class RevisionRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_patch: str = Field(min_length=1, max_length=12_000)


class RevisionRequestResponse(BaseModel):
    id: UUID
    chapter_id: UUID
    status: str
    replacement_branch_id: UUID | None


@router.post(
    "/{chapter_id}/revisions",
    response_model=RevisionRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_revision_request(
    chapter_id: UUID,
    payload: RevisionRequestInput,
    user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> RevisionRequestResponse:
    with tenant_connection(user) as connection:
        if if_match is not None:
            with connection.cursor() as cursor:
                cursor.execute("SELECT branch_id FROM chapters WHERE id = %s", (chapter_id,))
                branch_row = cursor.fetchone()
            if branch_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
                )
            _check_if_match(connection, UUID(str(cast(tuple[Any, ...], branch_row)[0])), if_match)
        with connection.cursor() as cursor:
            if idempotency_key is not None:
                cursor.execute(
                    "SELECT id, chapter_id, status, replacement_branch_id FROM chapter_revisions "
                    "WHERE requested_by_user_id = %s AND idempotency_key = %s",
                    (user.id, idempotency_key),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    values = cast(tuple[Any, ...], existing)
                    return RevisionRequestResponse(
                        id=UUID(str(values[0])),
                        chapter_id=UUID(str(values[1])),
                        status=str(values[2]),
                        replacement_branch_id=(
                            UUID(str(values[3])) if values[3] is not None else None
                        ),
                    )

            cursor.execute(
                "INSERT INTO chapter_revisions "
                "(chapter_id, requested_by_user_id, author_patch, status, idempotency_key) "
                "VALUES (%s, %s, %s, 'DRAFT', %s) "
                "RETURNING id, chapter_id, status, replacement_branch_id",
                (chapter_id, user.id, payload.author_patch, idempotency_key),
            )
            row = cursor.fetchone()
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Revision request failed"
        )
    values = cast(tuple[Any, ...], row)
    return RevisionRequestResponse(
        id=UUID(str(values[0])),
        chapter_id=UUID(str(values[1])),
        status=str(values[2]),
        replacement_branch_id=UUID(str(values[3])) if values[3] is not None else None,
    )


@router.get("/{chapter_id}/revisions", response_model=list[RevisionRequestResponse])
def list_revision_requests(chapter_id: UUID, user: CurrentUser) -> list[RevisionRequestResponse]:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, chapter_id, status, replacement_branch_id "
                "FROM chapter_revisions WHERE chapter_id = %s ORDER BY created_at DESC",
                (chapter_id,),
            )
            rows = cast(list[tuple[Any, ...]], cursor.fetchall())
    return [
        RevisionRequestResponse(
            id=UUID(str(row[0])),
            chapter_id=UUID(str(row[1])),
            status=str(row[2]),
            replacement_branch_id=UUID(str(row[3])) if row[3] is not None else None,
        )
        for row in rows
    ]
