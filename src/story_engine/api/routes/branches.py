"""Branch/arc timeline endpoints (read-only; branch creation is Track E's job-dispatch path)."""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection

router = APIRouter(prefix="/api/v1/arcs", tags=["branches"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class BranchResponse(BaseModel):
    id: UUID
    name: str
    status: str
    parent_branch_id: UUID | None
    chapter_count: int


@router.get("/{arc_id}/branches", response_model=list[BranchResponse])
def list_branches(arc_id: UUID, user: CurrentUser) -> list[BranchResponse]:
    """Return the branch tree/timeline for an arc. RLS scopes this to the caller's own arc."""

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT b.id, b.name, b.status, b.parent_branch_id, "
                "  (SELECT count(*) FROM chapters c WHERE c.branch_id = b.id) AS chapter_count "
                "FROM branches b WHERE b.arc_id = %s ORDER BY b.created_at",
                (arc_id,),
            )
            rows = cursor.fetchall()
    return [
        BranchResponse(
            id=UUID(str(row[0])),
            name=str(row[1]),
            status=str(row[2]),
            parent_branch_id=UUID(str(row[3])) if row[3] is not None else None,
            chapter_count=int(row[4]),
        )
        for row in cast(list[tuple[Any, ...]], rows)
    ]
