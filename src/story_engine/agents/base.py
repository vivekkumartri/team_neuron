"""Non-privileged agent adapter base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from story_engine.agents.provider import ModelProvider
from story_engine.security.prompt_safety import (
    AgentProposal,
    ProposalAction,
    delimit_untrusted_text,
)


class ProposalAgent(ABC):
    """Agents generate a proposal only; services own persistence and commits."""

    name: str
    system_prompt: str

    def __init__(self, provider: ModelProvider, *, model: str) -> None:
        self._provider = provider
        self._model = model

    def propose(self, *, chapter_id: UUID, input_text: str) -> AgentProposal:
        response = self._provider.complete(
            system_prompt=self.system_prompt,
            user_data=delimit_untrusted_text(input_text, source=self.name),
            model=self._model,
        )
        return AgentProposal(
            action=self.action(),
            chapter_id=chapter_id,
            rationale=f"{self.name} proposal is ready for service review.",
            proposed_text=response,
        )

    @abstractmethod
    def action(self) -> ProposalAction: ...
