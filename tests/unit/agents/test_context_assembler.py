from __future__ import annotations

from uuid import UUID

import pytest

from story_engine.agents.context_assembler import (
    ContextAssemblyError,
    assemble_character_context,
    select_active_cast,
)
from story_engine.agents.contracts import (
    BranchDirectorMemory,
    CharacterMemoryBuckets,
    EligibleCharacter,
)


def _character(identifier: int, score: int) -> EligibleCharacter:
    return EligibleCharacter(
        entity_id=UUID(int=identifier),
        public_summary=f"Character {identifier} is present.",
        relevance_score=score,
    )


def test_context_contains_only_assigned_character_private_memory() -> None:
    focal = _character(1, 100)
    other = _character(2, 90)
    context = assemble_character_context(
        branch_id=UUID(int=99),
        focal_character_id=focal.entity_id,
        branch_snapshot="The bridge has collapsed.",
        eligible_characters=[focal, other],
        character_memories={
            focal.entity_id: CharacterMemoryBuckets(core=("FOCAL_SECRET",)),
            other.entity_id: CharacterMemoryBuckets(core=("OTHER_SECRET",)),
        },
        director_memory=BranchDirectorMemory(summaries=("Keep tension high.",)),
    )

    serialized = context.model_dump_json()
    assert "FOCAL_SECRET" in serialized
    assert "OTHER_SECRET" not in serialized


def test_five_eligible_characters_are_bounded_and_deterministic() -> None:
    characters = [_character(identifier, 50) for identifier in range(1, 6)]

    selected = select_active_cast(characters)

    assert [character.entity_id for character in selected] == [
        UUID(int=value) for value in range(1, 5)
    ]


def test_focal_character_must_be_active() -> None:
    focal = _character(99, 1)
    high_relevance = [_character(identifier, 100 - identifier) for identifier in range(1, 6)]

    with pytest.raises(ContextAssemblyError, match="active cast"):
        assemble_character_context(
            branch_id=UUID(int=99),
            focal_character_id=focal.entity_id,
            branch_snapshot="A storm arrives.",
            eligible_characters=[*high_relevance, focal],
            character_memories={focal.entity_id: CharacterMemoryBuckets(core=("FOCAL",))},
            director_memory=BranchDirectorMemory(),
        )
