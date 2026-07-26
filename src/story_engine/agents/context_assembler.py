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
from story_engine.memory_graph.schema import FactNode, FactStatus

DEFAULT_MAX_FACTS = 10


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


def _select_top_k_facts(
    facts: Sequence[FactNode],
    *,
    branch_id: UUID,
    focal_character_id: UUID,
    max_facts: int,
) -> tuple[str, ...]:
    """Render a bounded, deterministic top-k slice of one character's ACTIVE facts.

    Enforces the same isolation boundary `character_memories` reads through
    `character_memories` and this function's caller already do: every fact
    must belong to the focal character on this branch, or the caller made a
    mistake building its query and this raises rather than silently leaking
    (or silently dropping) another character's memory.
    """

    for fact in facts:
        if fact.branch_id != branch_id or fact.character_id != focal_character_id:
            raise ContextAssemblyError(
                "Fact-layer input must be pre-scoped to the focal character's branch"
            )
    active = [fact for fact in facts if fact.status is FactStatus.ACTIVE]
    ranked = sorted(
        active,
        key=lambda fact: (
            -(fact.confidence if fact.confidence is not None else 0.0),
            fact.head,
            fact.relation,
            fact.tail,
        ),
    )
    return tuple(f"({fact.head}, {fact.relation}, {fact.tail})" for fact in ranked[:max_facts])


def assemble_character_context(
    *,
    branch_id: UUID,
    focal_character_id: UUID,
    branch_snapshot: str,
    eligible_characters: Sequence[EligibleCharacter],
    character_memories: Mapping[UUID, CharacterMemoryBuckets],
    director_memory: BranchDirectorMemory,
    max_active_characters: int = 4,
    focal_character_facts: Sequence[FactNode] | None = None,
    max_facts: int = DEFAULT_MAX_FACTS,
) -> CharacterDecisionContext:
    """Build a context without loading another character's private memory.

    `focal_character_facts` is optional fact-layer input (see
    docs/adr/0001-memgraphrag-adaptation.md): when provided, its top-`max_facts`
    ACTIVE triples are merged into the focal character's
    `CharacterMemoryBuckets.facts` bucket, alongside (not replacing) the
    existing flat `episodic` tuple. When omitted, behavior is identical to
    before this parameter existed.
    """

    focal_memory = character_memories.get(focal_character_id)
    if focal_memory is None:
        raise ContextAssemblyError("Focal character has no memory record on this branch")
    active_cast = select_active_cast(
        eligible_characters, max_active_characters=max_active_characters
    )
    active_ids = {character.entity_id for character in active_cast}
    if focal_character_id not in active_ids:
        raise ContextAssemblyError("Focal character must be part of the active cast")

    if focal_character_facts is not None:
        top_facts = _select_top_k_facts(
            focal_character_facts,
            branch_id=branch_id,
            focal_character_id=focal_character_id,
            max_facts=max_facts,
        )
        focal_memory = focal_memory.model_copy(update={"facts": top_facts})

    return CharacterDecisionContext(
        branch_id=branch_id,
        focal_character_id=focal_character_id,
        branch_snapshot=branch_snapshot,
        focal_memory=focal_memory,
        director_memory=director_memory,
        active_cast=active_cast,
    )

