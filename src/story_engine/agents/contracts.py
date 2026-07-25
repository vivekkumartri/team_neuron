"""Typed, minimal inputs for isolated agent decisions."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CharacterMemoryBuckets(BaseModel):
    """Private memory owned by exactly one character on one branch."""

    model_config = ConfigDict(frozen=True)

    core: tuple[str, ...] = Field(default=(), max_length=50)
    episodic: tuple[str, ...] = Field(default=(), max_length=50)
    screenplay: tuple[str, ...] = Field(default=(), max_length=50)


class BranchDirectorMemory(BaseModel):
    """Safe branch-level coordination memory; no character-private excerpts."""

    model_config = ConfigDict(frozen=True)

    summaries: tuple[str, ...] = Field(default=(), max_length=50)


class EligibleCharacter(BaseModel):
    """Public candidate metadata used for deterministic beat selection."""

    model_config = ConfigDict(frozen=True)

    entity_id: UUID
    public_summary: str = Field(min_length=1, max_length=500)
    relevance_score: int = Field(ge=0, le=100)


class CharacterDecisionContext(BaseModel):
    """The only private-character context an adapter is allowed to receive."""

    model_config = ConfigDict(frozen=True)

    branch_id: UUID
    focal_character_id: UUID
    branch_snapshot: str = Field(min_length=1, max_length=5_000)
    focal_memory: CharacterMemoryBuckets
    director_memory: BranchDirectorMemory
    active_cast: tuple[EligibleCharacter, ...] = Field(min_length=1, max_length=4)

