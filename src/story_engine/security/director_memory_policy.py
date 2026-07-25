"""Controls for the branch-scoped Director coordination memory."""

from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UnsafeDirectorMemory(ValueError):
    """Raised when Director coordination memory attempts to retain private data."""


_PRIVATE_MEMORY_MARKERS = re.compile(
    r"\b(?:hidden characteristic|unrevealed|private (?:memory|excerpt|thought)|"
    r"secret (?:memory|trait|fear)|character[_ -]?private)\b",
    re.IGNORECASE,
)


class DirectorMemoryRecord(BaseModel):
    """Public-to-branch coordination note, never a character's private memory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch_id: UUID
    summary: str = Field(min_length=1, max_length=1_000)
    source_character_ids: tuple[UUID, ...] = ()

    @field_validator("summary")
    @classmethod
    def reject_private_character_data(cls, value: str) -> str:
        if _PRIVATE_MEMORY_MARKERS.search(value):
            raise UnsafeDirectorMemory("Director memory cannot contain private character data")
        return value

