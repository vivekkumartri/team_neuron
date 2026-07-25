from story_engine.agents.base import ProposalAgent
from story_engine.agents.prompts.system import BUSINESS
from story_engine.security.prompt_safety import ProposalAction


class BusinessAgent(ProposalAgent):
    name = "business"
    system_prompt = BUSINESS

    def action(self) -> ProposalAction:
        return ProposalAction.REQUEST_REVIEW
