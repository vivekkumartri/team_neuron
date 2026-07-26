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
branch_cast_router = APIRouter(prefix="/api/v1/branches", tags=["cast"])
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
                # first branch joins the roster as a plain 'CHARACTER' — no
                # one is singled out as a protagonist. Generation still picks
                # one focal character per chapter (see `generation_job.py`),
                # but that's an ordering choice made at generation time, not
                # a fixed, unremovable role recorded here.
                cursor.execute(
                    "SELECT id FROM entities WHERE story_id = %s AND entity_type = 'character'",
                    (story_id,),
                )
                for (entity_id,) in cast(list[tuple[Any, ...]], cursor.fetchall()):
                    cursor.execute(
                        "INSERT INTO cast_members (story_id, entity_id, role) "
                        "VALUES (%s, %s, 'CHARACTER') ON CONFLICT (story_id, entity_id) DO NOTHING",
                        (story_id, entity_id),
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


class AddCastMemberRequest(BaseModel):
    name: str


@branch_cast_router.get("/{branch_id}/cast-members", response_model=list[CastMember])
def list_branch_cast_members(branch_id: UUID, user: CurrentUser) -> list[CastMember]:
    """The story's current cast, resolved from a branch id — the workspace

    screen only ever has a branch id in hand, not the story id.

    Self-healing: `CastLock.tsx` didn't call `lock_cast` for some time (fixed
    separately), so any story created during that window has character
    `entities` but zero `cast_members` rows. Rather than leaving those
    stories permanently stuck with an empty cast panel, detect an unlocked
    story here and lock it on the fly — `lock_cast` is already idempotent
    and safe to call from a GET in this case since it only ever backfills
    from existing `entities`, never creates or changes story content.
    """

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT s.id, s.cast_locked_at FROM branches b "
                "JOIN stories s ON s.id = b.story_id WHERE b.id = %s",
                (branch_id,),
            )
            story_row = cursor.fetchone()
            if story_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found"
                )
            story_id, cast_locked_at = cast(tuple[Any, ...], story_row)

        if cast_locked_at is None:
            lock_cast(UUID(str(story_id)), user)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT cm.entity_id, e.name, cm.role FROM cast_members cm "
                "JOIN entities e ON e.id = cm.entity_id "
                "JOIN branches b ON b.story_id = cm.story_id "
                "WHERE b.id = %s ORDER BY cm.created_at",
                (branch_id,),
            )
            rows = cast(list[tuple[Any, ...]], cursor.fetchall())
    return [
        CastMember(entity_id=UUID(str(row[0])), name=str(row[1]), role=str(row[2])) for row in rows
    ]


@branch_cast_router.post(
    "/{branch_id}/cast-members", response_model=CastMember, status_code=status.HTTP_201_CREATED
)
def add_cast_member(
    branch_id: UUID, payload: AddCastMemberRequest, user: CurrentUser
) -> CastMember:
    """Introduce a new character to the story mid-run.

    Every cast member is a plain 'CHARACTER' — no protagonist/supporting
    distinction. `entities` still has PUBLIC INSERT (migration 0008 only
    revoked UPDATE/DELETE), so this plain INSERT matches the existing
    canonical-write boundary the same way `create_story` already does.
    """

    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required"
        )

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT story_id FROM branches WHERE id = %s", (branch_id,))
            branch_row = cursor.fetchone()
            if branch_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found"
                )
            story_id = cast(tuple[Any, ...], branch_row)[0]

            try:
                cursor.execute(
                    "INSERT INTO entities (story_id, name, entity_type, founding_branch_id) "
                    "VALUES (%s, %s, 'character', %s) RETURNING id",
                    (story_id, name, branch_id),
                )
            except Exception as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A character with that name already exists in this story",
                ) from error
            entity_id = cast(tuple[Any, ...], cursor.fetchone())[0]

            cursor.execute(
                "INSERT INTO cast_members (story_id, entity_id, role) VALUES (%s, %s, 'CHARACTER')",
                (story_id, entity_id),
            )
        connection.commit()

    return CastMember(entity_id=UUID(str(entity_id)), name=name, role="CHARACTER")


@branch_cast_router.delete(
    "/{branch_id}/cast-members/{entity_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_cast_member(branch_id: UUID, entity_id: UUID, user: CurrentUser) -> None:
    """Remove a character from the story's active cast.

    Every character can be removed — there is no protagonist role that's
    special-cased or protected. This deletes only the `cast_members` row,
    never the `entities` row itself — `entities` has no DELETE grant for
    PUBLIC (migration 0008) and, more importantly, published
    chapters/scenes/dialogue may already reference this character; removing
    it from the cast should stop it being offered for future chapters
    without rewriting history. The one thing still blocked is emptying the
    cast entirely — generation needs at least one character to write about.
    """

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT cm.story_id FROM cast_members cm "
                "JOIN branches b ON b.story_id = cm.story_id "
                "WHERE b.id = %s AND cm.entity_id = %s",
                (branch_id, entity_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Cast member not found"
                )
            story_id = cast(tuple[Any, ...], row)[0]

            cursor.execute("SELECT count(*) FROM cast_members WHERE story_id = %s", (story_id,))
            member_count = cast(tuple[Any, ...], cursor.fetchone())[0]
            if member_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "A story needs at least one character — add another before removing "
                        "this one"
                    ),
                )

            cursor.execute(
                "DELETE FROM cast_members WHERE story_id = %s AND entity_id = %s",
                (story_id, entity_id),
            )
        connection.commit()
