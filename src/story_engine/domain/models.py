"""Stable, provider-independent domain types."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChapterStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    EVALUATING = "EVALUATING"
    PUBLISHED = "PUBLISHED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class BranchStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class CanonEventStatus(StrEnum):
    DRAFT = "DRAFT"
    EVALUATING = "EVALUATING"
    APPROVED = "APPROVED"
    ADJUSTED = "ADJUSTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ProgressionMode(StrEnum):
    CONTINUE = "CONTINUE"
    EDIT_TRAITS = "EDIT_TRAITS"
    REWIND = "REWIND"


class ChapterRef(BaseModel):
    """Minimal immutable chapter identity used at service boundaries."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    branch_id: UUID
    chapter_index: int = Field(ge=1)
    status: ChapterStatus


class ProgressionRequest(BaseModel):
    """Exactly one author-selected way to advance a published chapter."""

    # None is the explicit "start Chapter 1" sentinel. All later actions
    # carry an immutable published chapter id.
    chapter_id: UUID | None = None
    focal_entity_id: UUID
    mode: ProgressionMode
    trait_change: str | None = Field(default=None, max_length=2_000)
    rewind_to_chapter_id: UUID | None = None
