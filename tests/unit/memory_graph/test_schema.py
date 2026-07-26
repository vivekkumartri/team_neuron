from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from story_engine.memory_graph.schema import (
    FactNode,
    FactStatus,
    PassageNode,
    SchemaCategory,
    SchemaNode,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "memgraphrag_memory_reference.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_schema_node_round_trips_against_reference_fixture() -> None:
    payload = _fixture()["schema_nodes"][0]

    node = SchemaNode.model_validate(payload)

    assert node.name == "Character"
    assert node.category is SchemaCategory.ENTITY_TYPE
    round_tripped = SchemaNode.model_validate_json(node.model_dump_json())
    assert round_tripped == node


def test_fact_node_round_trips_against_reference_fixture() -> None:
    payload = _fixture()["fact_nodes"][0]

    fact = FactNode.model_validate(payload)

    assert fact.as_triple() == ("Mira", "owns", "a bronze key")
    assert fact.status is FactStatus.ACTIVE
    round_tripped = FactNode.model_validate_json(fact.model_dump_json())
    assert round_tripped == fact


def test_passage_node_round_trips_against_reference_fixture() -> None:
    payload = _fixture()["passage_nodes"][0]

    passage = PassageNode.model_validate(payload)

    assert passage.source_chapter_id == UUID("00000000-0000-0000-0000-000000000003")
    round_tripped = PassageNode.model_validate_json(passage.model_dump_json())
    assert round_tripped == passage


def test_superseded_by_requires_superseded_status() -> None:
    with pytest.raises(ValidationError, match="superseded_by"):
        FactNode(
            branch_id=UUID(int=1),
            character_id=UUID(int=2),
            head="Mira",
            head_type="Character",
            relation="owns",
            relation_type="owns",
            tail="a bronze key",
            tail_type="Object",
            status=FactStatus.ACTIVE,
            superseded_by=UUID(int=3),
        )


def test_confidence_must_be_a_probability() -> None:
    with pytest.raises(ValidationError):
        FactNode(
            branch_id=UUID(int=1),
            character_id=UUID(int=2),
            head="Mira",
            head_type="Character",
            relation="owns",
            relation_type="owns",
            tail="a bronze key",
            tail_type="Object",
            confidence=1.5,
        )
