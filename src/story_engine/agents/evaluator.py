from story_engine.agents.base import ProposalAgent
from story_engine.agents.prompts.system import EVALUATOR
from story_engine.security.prompt_safety import ProposalAction


class EvaluatorAgent(ProposalAgent):
    name = "evaluator"
    system_prompt = EVALUATOR

    def action(self) -> ProposalAction:
        return ProposalAction.REQUEST_REVIEW
