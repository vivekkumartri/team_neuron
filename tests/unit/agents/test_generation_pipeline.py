from __future__ import annotations

from uuid import uuid4

import pytest

from story_engine.domain.policy_models import PolicyDecision, PolicyResult, PolicySubject
from story_engine.services.generation_pipeline import (
    EvaluationOutcome,
    GenerationRejected,
    generate_evaluated_candidate,
)


class Drafts:
    def draft(self, *, focal_character_id: object, attempt: int) -> str:
        return f"Original scene attempt {attempt}."


class Evaluator:
    def __init__(self, outcomes: list[EvaluationOutcome]) -> None:
        self.outcomes = outcomes

    def evaluate(self, candidate: object) -> EvaluationOutcome:
        return self.outcomes.pop(0)


class Allows:
    def assess(self, text: str, subject: PolicySubject) -> PolicyResult:
        return PolicyResult(decision=PolicyDecision.ALLOW, message="ok")


def test_major_divergence_regenerates_then_approves() -> None:
    result = generate_evaluated_candidate(
        job_id=uuid4(), branch_id=uuid4(), focal_character_id=uuid4(), storyteller=Drafts(),
        evaluator=Evaluator([EvaluationOutcome.MAJOR_DIVERGENCE, EvaluationOutcome.APPROVED]),
        policy=Allows(),
    )
    assert result.status.value == "APPROVED"
    assert result.screenplay.endswith("2.")


def test_retries_exhaust_without_publication() -> None:
    with pytest.raises(GenerationRejected):
        generate_evaluated_candidate(
            job_id=uuid4(), branch_id=uuid4(), focal_character_id=uuid4(), storyteller=Drafts(),
            evaluator=Evaluator([EvaluationOutcome.MAJOR_DIVERGENCE] * 3), policy=Allows(),
        )
