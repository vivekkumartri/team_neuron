from __future__ import annotations

from uuid import UUID

import pytest

from story_engine.memory_graph.conflict import (
    ConflictCategory,
    ConflictResolutionAction,
    classify_conflict,
    detect_conflicts,
    facts_requiring_continuity_flag,
    find_candidate_pairs,
)
from story_engine.memory_graph.schema import FactNode, FactStatus

BRANCH_ID = UUID(int=1)
CHARACTER_ID = UUID(int=2)


def _fact(
    head: str, relation: str, tail: str, *, status: FactStatus = FactStatus.ACTIVE
) -> FactNode:
    return FactNode(
        branch_id=BRANCH_ID,
        character_id=CHARACTER_ID,
        head=head,
        head_type="Character",
        relation=relation,
        relation_type=relation,
        tail=tail,
        tail_type="Object",
        status=status,
    )


class _StubProvider:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, *, system_prompt: str, user_data: str, model: str) -> str:
        return self._response


def test_candidate_pairs_require_shared_head_or_tail() -> None:
    mutual = _fact("Mira", "owns", "a bronze key")
    unrelated = _fact("Kai", "fears", "the dark")

    pairs = find_candidate_pairs([mutual, unrelated])

    assert pairs == ()


def test_candidate_pairs_match_on_shared_subject() -> None:
    owns = _fact("Mira", "owns", "a bronze key")
    lost = _fact("Mira", "lost", "a bronze key")

    pairs = find_candidate_pairs([owns, lost])

    assert pairs == ((owns, lost),)


def test_exact_duplicate_triples_are_not_candidates() -> None:
    fact = _fact("Mira", "owns", "a bronze key")
    duplicate = _fact("Mira", "owns", "a bronze key")

    pairs = find_candidate_pairs([fact, duplicate])

    assert pairs == ()


def test_superseded_facts_are_excluded_from_candidates() -> None:
    active = _fact("Mira", "owns", "a bronze key")
    superseded = _fact("Mira", "lost", "a bronze key", status=FactStatus.SUPERSEDED)

    pairs = find_candidate_pairs([active, superseded])

    assert pairs == ()


def test_classify_conflict_parses_mutual_contradiction() -> None:
    provider = _StubProvider(
        '{"category": "MUTUAL", "action": "FLAG_FOR_REVIEW", '
        '"rationale": "Mira cannot both own and have lost the same key."}'
    )
    fact_a = _fact("Mira", "owns", "a bronze key")
    fact_b = _fact("Mira", "lost", "a bronze key")

    result = classify_conflict(provider, model="gpt-4o-mini", fact_a=fact_a, fact_b=fact_b)

    assert result.category is ConflictCategory.MUTUAL
    assert result.action is ConflictResolutionAction.FLAG_FOR_REVIEW


def test_classify_conflict_rejects_malformed_json() -> None:
    provider = _StubProvider("not json")
    fact_a = _fact("Mira", "owns", "a bronze key")
    fact_b = _fact("Mira", "lost", "a bronze key")

    with pytest.raises(ValueError, match="not valid JSON"):
        classify_conflict(provider, model="gpt-4o-mini", fact_a=fact_a, fact_b=fact_b)


def test_detect_conflicts_and_continuity_filter_end_to_end() -> None:
    provider = _StubProvider(
        '{"category": "MUTUAL", "action": "FLAG_FOR_REVIEW", '
        '"rationale": "Direct contradiction."}'
    )
    owns = _fact("Mira", "owns", "a bronze key")
    lost = _fact("Mira", "lost", "a bronze key")

    conflicts = detect_conflicts(provider, model="gpt-4o-mini", facts=[owns, lost])
    flagged = facts_requiring_continuity_flag(conflicts)

    assert len(conflicts) == 1
    assert flagged == conflicts


def test_granularity_keep_both_is_not_flagged() -> None:
    provider = _StubProvider(
        '{"category": "GRANULARITY", "action": "KEEP_BOTH", '
        '"rationale": "One is a more specific restatement of the other."}'
    )
    owns_key = _fact("Mira", "owns", "a key")
    owns_bronze_key = _fact("Mira", "owns", "a bronze key")

    conflicts = detect_conflicts(provider, model="gpt-4o-mini", facts=[owns_key, owns_bronze_key])

    assert conflicts == ()
