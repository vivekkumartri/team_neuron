from __future__ import annotations

from uuid import UUID

import pytest

from story_engine.agents.contracts import CharacterMemoryBuckets
from story_engine.agents.provider import ModelProviderError
from story_engine.memory_graph.relation_extract import (
    RelationExtractionError,
    extract_facts_from_passage,
    passage_text_from_episodic_memory,
)

BRANCH_ID = UUID(int=1)
CHARACTER_ID = UUID(int=2)


class _StubProvider:
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call: dict[str, str] | None = None

    def complete(self, *, system_prompt: str, user_data: str, model: str) -> str:
        self.last_call = {"system_prompt": system_prompt, "user_data": user_data, "model": model}
        return self._response


class _FailingProvider:
    def complete(self, *, system_prompt: str, user_data: str, model: str) -> str:
        raise ModelProviderError("provider unavailable")


def test_extracts_valid_triples_from_json_array_response() -> None:
    provider = _StubProvider(
        '[{"head": "Mira", "head_type": "Character", "relation": "owns", '
        '"relation_type": "owns", "tail": "a bronze key", "tail_type": "Object", '
        '"confidence": 0.9}]'
    )

    facts = extract_facts_from_passage(
        provider,
        model="gpt-4o-mini",
        branch_id=BRANCH_ID,
        character_id=CHARACTER_ID,
        passage_text="Mira pocketed the bronze key.",
    )

    assert len(facts) == 1
    assert facts[0].as_triple() == ("Mira", "owns", "a bronze key")
    assert facts[0].confidence == pytest.approx(0.9)
    assert facts[0].branch_id == BRANCH_ID
    assert facts[0].character_id == CHARACTER_ID


def test_strips_markdown_fences_before_parsing() -> None:
    provider = _StubProvider(
        "```json\n"
        '[{"head": "Mira", "head_type": "Character", "relation": "fears", '
        '"relation_type": "fears", "tail": "the dark", "tail_type": "Concept", '
        '"confidence": 0.5}]'
        "\n```"
    )

    facts = extract_facts_from_passage(
        provider,
        model="gpt-4o-mini",
        branch_id=BRANCH_ID,
        character_id=CHARACTER_ID,
        passage_text="Mira flinched at the dark hallway.",
    )

    assert len(facts) == 1
    assert facts[0].relation == "fears"


def test_empty_array_response_yields_no_facts() -> None:
    provider = _StubProvider("[]")

    facts = extract_facts_from_passage(
        provider,
        model="gpt-4o-mini",
        branch_id=BRANCH_ID,
        character_id=CHARACTER_ID,
        passage_text="The weather was unremarkable.",
    )

    assert facts == ()


def test_malformed_json_response_raises_relation_extraction_error() -> None:
    provider = _StubProvider("not json at all")

    with pytest.raises(RelationExtractionError):
        extract_facts_from_passage(
            provider,
            model="gpt-4o-mini",
            branch_id=BRANCH_ID,
            character_id=CHARACTER_ID,
            passage_text="Mira pocketed the bronze key.",
        )


def test_one_malformed_triple_does_not_discard_the_rest() -> None:
    provider = _StubProvider(
        '[{"head": "missing_fields_only"}, '
        '{"head": "Mira", "head_type": "Character", "relation": "owns", '
        '"relation_type": "owns", "tail": "a bronze key", "tail_type": "Object"}]'
    )

    facts = extract_facts_from_passage(
        provider,
        model="gpt-4o-mini",
        branch_id=BRANCH_ID,
        character_id=CHARACTER_ID,
        passage_text="Mira pocketed the bronze key.",
    )

    assert len(facts) == 1
    assert facts[0].head == "Mira"


def test_provider_error_propagates_unwrapped() -> None:
    with pytest.raises(ModelProviderError):
        extract_facts_from_passage(
            _FailingProvider(),
            model="gpt-4o-mini",
            branch_id=BRANCH_ID,
            character_id=CHARACTER_ID,
            passage_text="Mira pocketed the bronze key.",
        )


def test_passage_text_from_episodic_memory_joins_recent_entries() -> None:
    memory = CharacterMemoryBuckets(episodic=("first", "second", "third"))

    text = passage_text_from_episodic_memory(memory, limit=2)

    assert text == "second\nthird"
