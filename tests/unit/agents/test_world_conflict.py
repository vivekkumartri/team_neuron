from __future__ import annotations

from uuid import UUID

from story_engine.agents.world import WorldAgent
from story_engine.memory_graph.schema import FactNode
from story_engine.security.prompt_safety import ProposalAction

BRANCH_ID = UUID(int=1)
CHARACTER_ID = UUID(int=2)


def _fact(head: str, relation: str, tail: str) -> FactNode:
    return FactNode(
        branch_id=BRANCH_ID,
        character_id=CHARACTER_ID,
        head=head,
        head_type="Character",
        relation=relation,
        relation_type=relation,
        tail=tail,
        tail_type="Object",
    )


class _StubProvider:
    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, *, system_prompt: str, user_data: str, model: str) -> str:
        return self._response


def test_world_agent_action_is_unchanged_flag_continuity() -> None:
    agent = WorldAgent(_StubProvider("[]"), model="gpt-4o-mini")

    assert agent.action() is ProposalAction.FLAG_CONTINUITY


def test_find_continuity_conflicts_surfaces_mutual_contradiction() -> None:
    provider = _StubProvider(
        '{"category": "MUTUAL", "action": "FLAG_FOR_REVIEW", '
        '"rationale": "Direct contradiction."}'
    )
    agent = WorldAgent(provider, model="gpt-4o-mini")
    owns = _fact("Mira", "owns", "a bronze key")
    lost = _fact("Mira", "lost", "a bronze key")

    flagged = agent.find_continuity_conflicts([owns, lost])

    assert len(flagged) == 1
    fact_a, fact_b, result = flagged[0]
    assert {fact_a, fact_b} == {owns, lost}
    assert result.category.value == "MUTUAL"


def test_find_continuity_conflicts_empty_when_no_candidates() -> None:
    provider = _StubProvider("{}")
    agent = WorldAgent(provider, model="gpt-4o-mini")
    unrelated_a = _fact("Mira", "owns", "a bronze key")
    unrelated_b = _fact("Kai", "fears", "the dark")

    flagged = agent.find_continuity_conflicts([unrelated_a, unrelated_b])

    assert flagged == ()
