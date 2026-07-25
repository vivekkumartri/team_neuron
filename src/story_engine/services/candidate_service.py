"""In-memory candidate contract; persistence adapters store the durable equivalent."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CandidateStatus(StrEnum):
    STAGED = "STAGED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class CandidateChapter(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: UUID
    branch_id: UUID
    focal_character_id: UUID
    screenplay: str = Field(min_length=1, max_length=12_000)
    status: CandidateStatus = CandidateStatus.STAGED
