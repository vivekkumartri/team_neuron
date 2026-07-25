from story_engine.agents.base import ProposalAgent
from story_engine.agents.prompts.system import DIRECTOR
from story_engine.security.prompt_safety import ProposalAction


class DirectorAgent(ProposalAgent):
    name = "director"
    system_prompt = DIRECTOR

    def action(self) -> ProposalAction:
        return ProposalAction.SUGGEST_SCENE
