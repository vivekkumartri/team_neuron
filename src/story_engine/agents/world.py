from __future__ import annotations

from collections.abc import Sequence

from story_engine.agents.base import ProposalAgent
from story_engine.agents.prompts.system import WORLD
from story_engine.memory_graph.conflict import (
    ConflictResult,
    detect_conflicts,
    facts_requiring_continuity_flag,
)
from story_engine.memory_graph.schema import FactNode
from story_engine.security.prompt_safety import ProposalAction


class WorldAgent(ProposalAgent):
    name = "world"
    system_prompt = WORLD

    def action(self) -> ProposalAction:
        return ProposalAction.FLAG_CONTINUITY

    def find_continuity_conflicts(
        self, facts: Sequence[FactNode]
    ) -> tuple[tuple[FactNode, FactNode, ConflictResult], ...]:
        """Run fact-graph conflict detection and keep only what should FLAG_CONTINUITY.

        `facts` must already be scoped to one branch/character (the same
        boundary `find_candidate_pairs` expects) -- this method does not
        itself enforce isolation across characters, matching how `action()`
        above has never taken cross-character input either.
        """

        conflicts = detect_conflicts(self._provider, model=self._model, facts=facts)
        return facts_requiring_continuity_flag(conflicts)
