from story_engine.agents.base import ProposalAgent
from story_engine.agents.prompts.system import STORYTELLER
from story_engine.security.prompt_safety import ProposalAction


class StorytellerAgent(ProposalAgent):
    name = "storyteller"
    system_prompt = STORYTELLER

    def action(self) -> ProposalAction:
        return ProposalAction.SUGGEST_SCENE
