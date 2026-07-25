"""Branch-fork invariants for persistence services."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BranchFork(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_branch_id: UUID
    forked_from_chapter_id: UUID
    child_name: str = Field(min_length=1, max_length=120)


def inherited_state_cutoff(fork: BranchFork) -> tuple[UUID, UUID]:
    """Persistence callers must read parent state only through this chapter cutoff."""

    return fork.parent_branch_id, fork.forked_from_chapter_id
