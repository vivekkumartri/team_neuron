from __future__ import annotations

from uuid import UUID

import pytest

from story_engine.agents.context_assembler import (
    ContextAssemblyError,
    assemble_character_context,
)
from story_engine.agents.contracts import (
    BranchDirectorMemory,
    CharacterMemoryBuckets,
    EligibleCharacter,
)
from story_engine.memory_graph.schema import FactNode, FactStatus

BRANCH_ID = UUID(int=99)


def _character(identifier: int, score: int) -> EligibleCharacter:
    return EligibleCharacter(
        entity_id=UUID(int=identifier),
        public_summary=f"Character {identifier} is present.",
        relevance_score=score,
    )


def _fact(
    character_id: UUID,
    head: str,
    relation: str,
    tail: str,
    *,
    confidence: float | None = None,
    status: FactStatus = FactStatus.ACTIVE,
    branch_id: UUID = BRANCH_ID,
) -> FactNode:
    return FactNode(
        branch_id=branch_id,
        character_id=character_id,
        head=head,
        head_type="Character",
        relation=relation,
        relation_type=relation,
        tail=tail,
        tail_type="Object",
        confidence=confidence,
        status=status,
    )


def _base_kwargs(focal: EligibleCharacter, other: EligibleCharacter) -> dict:
    return dict(
        branch_id=BRANCH_ID,
        focal_character_id=focal.entity_id,
        branch_snapshot="The bridge has collapsed.",
        eligible_characters=[focal, other],
        character_memories={
            focal.entity_id: CharacterMemoryBuckets(core=("FOCAL_CORE",)),
            other.entity_id: CharacterMemoryBuckets(core=("OTHER_CORE",)),
        },
        director_memory=BranchDirectorMemory(),
    )


def test_existing_tests_still_pass_when_facts_are_omitted() -> None:
    focal = _character(1, 100)
    other = _character(2, 90)

    context = assemble_character_context(**_base_kwargs(focal, other))

    assert context.focal_memory.facts == ()


def test_top_k_facts_are_injected_for_focal_character_only() -> None:
    focal = _character(1, 100)
    other = _character(2, 90)
    facts = [
        _fact(focal.entity_id, "Mira", "owns", "a bronze key", confidence=0.9),
        _fact(focal.entity_id, "Mira", "fears", "the dark", confidence=0.4),
    ]

    context = assemble_character_context(
        **_base_kwargs(focal, other),
        focal_character_facts=facts,
    )

    serialized = context.model_dump_json()
    assert "bronze key" in serialized
    assert "OTHER_CORE" not in serialized
    assert context.focal_memory.facts[0] == "(Mira, owns, a bronze key)"


def test_facts_are_bounded_by_max_facts() -> None:
    focal = _character(1, 100)
    other = _character(2, 90)
    facts = [
        _fact(focal.entity_id, "Mira", f"relation_{i}", f"tail_{i}", confidence=i / 10)
        for i in range(5)
    ]

    context = assemble_character_context(
        **_base_kwargs(focal, other),
        focal_character_facts=facts,
        max_facts=2,
    )

    assert len(context.focal_memory.facts) == 2
    # Highest confidence (relation_4/tail_4) ranked first.
    assert "tail_4" in context.focal_memory.facts[0]


def test_superseded_facts_are_excluded() -> None:
    focal = _character(1, 100)
    other = _character(2, 90)
    facts = [
        _fact(focal.entity_id, "Mira", "owns", "a bronze key", status=FactStatus.SUPERSEDED),
    ]

    context = assemble_character_context(
        **_base_kwargs(focal, other),
        focal_character_facts=facts,
    )

    assert context.focal_memory.facts == ()


def test_facts_belonging_to_another_character_raise_isolation_error() -> None:
    focal = _character(1, 100)
    other = _character(2, 90)
    leaked_facts = [_fact(other.entity_id, "Kai", "fears", "the dark")]

    with pytest.raises(ContextAssemblyError, match="pre-scoped"):
        assemble_character_context(
            **_base_kwargs(focal, other),
            focal_character_facts=leaked_facts,
        )


def test_facts_belonging_to_another_branch_raise_isolation_error() -> None:
    focal = _character(1, 100)
    other = _character(2, 90)
    wrong_branch_facts = [
        _fact(focal.entity_id, "Mira", "owns", "a bronze key", branch_id=UUID(int=1))
    ]

    with pytest.raises(ContextAssemblyError, match="pre-scoped"):
        assemble_character_context(
            **_base_kwargs(focal, other),
            focal_character_facts=wrong_branch_facts,
        )
