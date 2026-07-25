from story_engine.agents.base import ProposalAgent
from story_engine.agents.prompts.system import WORLD
from story_engine.security.prompt_safety import ProposalAction


class WorldAgent(ProposalAgent):
    name = "world"
    system_prompt = WORLD

    def action(self) -> ProposalAction:
        return ProposalAction.FLAG_CONTINUITY
