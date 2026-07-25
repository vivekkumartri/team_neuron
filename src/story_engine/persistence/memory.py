"""Branch-aware memory read boundaries."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemoryReadScope(BaseModel):
    model_config = ConfigDict(frozen=True)

    branch_id: UUID
    character_id: UUID
    visible_through_chapter_id: UUID | None = None


def memory_visibility_predicate(scope: MemoryReadScope) -> tuple[UUID, UUID, UUID | None]:
    """Repository implementations use this to prevent reads past a fork cutoff."""

    return scope.branch_id, scope.character_id, scope.visible_through_chapter_id
