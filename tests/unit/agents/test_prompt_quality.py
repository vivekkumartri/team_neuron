from __future__ import annotations

from story_engine.agents.prompts import system


def test_every_agent_prompt_has_required_safety_boundary() -> None:
    prompts = (system.DIRECTOR, system.WORLD, system.STORYTELLER, system.EVALUATOR, system.BUSINESS)

    for prompt in prompts:
        assert system.PROMPT_VERSION in prompt
        assert "hidden facts" in prompt
        assert "write canon" in prompt
