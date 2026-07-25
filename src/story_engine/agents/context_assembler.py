"""Tenant-safe, character-isolated context assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from story_engine.agents.contracts import (
    BranchDirectorMemory,
    CharacterDecisionContext,
    CharacterMemoryBuckets,
    EligibleCharacter,
)


class ContextAssemblyError(ValueError):
    """The requested focal character cannot safely receive a decision context."""


def select_active_cast(
    eligible_characters: Sequence[EligibleCharacter], *, max_active_characters: int = 4
) -> tuple[EligibleCharacter, ...]:
    """Select a stable, bounded public cast for one beat."""

    if max_active_characters < 1:
        raise ValueError("max_active_characters must be at least one")
    return tuple(
        sorted(
            eligible_characters,
            key=lambda character: (-character.relevance_score, str(character.entity_id)),
        )[:max_active_characters]
    )


def assemble_character_context(
    *,
    branch_id: UUID,
    focal_character_id: UUID,
    branch_snapshot: str,
    eligible_characters: Sequence[EligibleCharacter],
    character_memories: Mapping[UUID, CharacterMemoryBuckets],
    director_memory: BranchDirectorMemory,
    max_active_characters: int = 4,
) -> CharacterDecisionContext:
    """Build a context without loading another character's private memory."""

    focal_memory = character_memories.get(focal_character_id)
    if focal_memory is None:
        raise ContextAssemblyError("Focal character has no memory record on this branch")
    active_cast = select_active_cast(
        eligible_characters, max_active_characters=max_active_characters
    )
    active_ids = {character.entity_id for character in active_cast}
    if focal_character_id not in active_ids:
        raise ContextAssemblyError("Focal character must be part of the active cast")
    return CharacterDecisionContext(
        branch_id=branch_id,
        focal_character_id=focal_character_id,
        branch_snapshot=branch_snapshot,
        focal_memory=focal_memory,
        director_memory=director_memory,
        active_cast=active_cast,
    )

