"""Cast-lock and family-tree summary (Track 1 / plan P1.5).

Locking the cast is idempotent — a second `POST` returns the existing lock
timestamp and roster rather than erroring or re-locking, since the frontend
(`CastLock.tsx`) may retry on a flaky connection. Cast membership itself is
recorded in `cast_members` (migration 0011); this route never edits
`entities` or `branch_entity_states` directly, matching the rest of this
codebase's canonical-write boundary.
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection

router = APIRouter(prefix="/api/v1/stories", tags=["cast"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class CastMember(BaseModel):
    entity_id: UUID
    name: str
    role: str


class CastLockResponse(BaseModel):
    story_id: UUID
    cast_locked_at: str
    members: list[CastMember]


@router.post("/{story_id}/cast-lock", response_model=CastLockResponse)
def lock_cast(story_id: UUID, user: CurrentUser) -> CastLockResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT cast_locked_at FROM stories WHERE id = %s", (story_id,))
            story_row = cursor.fetchone()
            if story_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

            already_locked = cast(tuple[Any, ...], story_row)[0] is not None
            if not already_locked:
                # First lock: every character entity founded on this story's
                # first branch joins the roster, protagonist first.
                # The protagonist is always the earliest-created character
                # entity on the story (see `stories.py`'s `create_story`,
                # which inserts the protagonist-flagged cast member first
                # regardless of its position in the submitted `cast` array —
                # the same convention `list_stories`'s
                # `initial_focal_entity_id` subquery relies on). This is not
                # a literal name match, so it works for any real character
                # name, not just a hardcoded "Protagonist" entity.
                cursor.execute(
                    "SELECT e.id, e.name, "
                    "CASE WHEN e.id = ("
                    "  SELECT id FROM entities WHERE story_id = %s AND entity_type = 'character' "
                    "  ORDER BY created_at LIMIT 1"
                    ") THEN 'PROTAGONIST' ELSE 'SUPPORTING' END "
                    "FROM entities e WHERE e.story_id = %s AND e.entity_type = 'character'",
                    (story_id, story_id),
                )
                for entity_id, _name, role in cast(list[tuple[Any, ...]], cursor.fetchall()):
                    cursor.execute(
                        "INSERT INTO cast_members (story_id, entity_id, role) "
                        "VALUES (%s, %s, %s) ON CONFLICT (story_id, entity_id) DO NOTHING",
                        (story_id, entity_id, role),
                    )
                cursor.execute(
                    "UPDATE stories SET cast_locked_at = now() WHERE id = %s "
                    "RETURNING cast_locked_at",
                    (story_id,),
                )
                locked_at = cast(tuple[Any, ...], cursor.fetchone())[0]
            else:
                locked_at = cast(tuple[Any, ...], story_row)[0]

            cursor.execute(
                "SELECT cm.entity_id, e.name, cm.role FROM cast_members cm "
                "JOIN entities e ON e.id = cm.entity_id WHERE cm.story_id = %s "
                "ORDER BY cm.created_at",
                (story_id,),
            )
            members = [
                CastMember(entity_id=UUID(str(row[0])), name=str(row[1]), role=str(row[2]))
                for row in cast(list[tuple[Any, ...]], cursor.fetchall())
            ]
        connection.commit()

    return CastLockResponse(story_id=story_id, cast_locked_at=str(locked_at), members=members)


class FamilyTreeRelationship(BaseModel):
    from_entity_id: UUID
    from_name: str
    to_entity_id: UUID
    to_name: str
    relationship_type: str


class FamilyTreeResponse(BaseModel):
    story_id: UUID
    relationships: list[FamilyTreeRelationship]


_FAMILY_RELATIONSHIP_TYPES = ("PARENT_OF", "CHILD_OF", "SIBLING_OF", "SPOUSE_OF")


@router.get("/{story_id}/family-tree", response_model=FamilyTreeResponse)
def get_family_tree(story_id: UUID, user: CurrentUser) -> FamilyTreeResponse:
    """Family-only relationships across the story's founding branch — a

    summary for cast confirmation, not a full relationship graph (that's
    `world.py`'s read-only branch state).
    """

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT br.from_entity_id, ef.name, br.to_entity_id, et.name, br.relationship_type "
                "FROM branch_relationships br "
                "JOIN branches b ON b.id = br.branch_id "
                "JOIN entities ef ON ef.id = br.from_entity_id "
                "JOIN entities et ON et.id = br.to_entity_id "
                "WHERE b.story_id = %s AND br.relationship_type = ANY(%s) "
                "ORDER BY br.version DESC",
                (story_id, list(_FAMILY_RELATIONSHIP_TYPES)),
            )
            rows = cast(list[tuple[Any, ...]], cursor.fetchall())

    return FamilyTreeResponse(
        story_id=story_id,
        relationships=[
            FamilyTreeRelationship(
                from_entity_id=UUID(str(row[0])),
                from_name=str(row[1]),
                to_entity_id=UUID(str(row[2])),
                to_name=str(row[3]),
                relationship_type=str(row[4]),
            )
            for row in rows
        ],
    )
