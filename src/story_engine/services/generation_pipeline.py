"""Bounded, evaluator-gated generation orchestration."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from story_engine.domain.policy_models import PolicyDecision, PolicySubject
from story_engine.security.content_policy import ModerationAdapter
from story_engine.services.candidate_service import CandidateChapter, CandidateStatus


class EvaluationOutcome(StrEnum):
    APPROVED = "APPROVED"
    MINOR_DIVERGENCE = "MINOR_DIVERGENCE"
    MAJOR_DIVERGENCE = "MAJOR_DIVERGENCE"


class StoryDraftingAdapter(Protocol):
    def draft(self, *, focal_character_id: UUID, attempt: int) -> str: ...


class EvaluatorAdapter(Protocol):
    def evaluate(self, candidate: CandidateChapter) -> EvaluationOutcome: ...


class GenerationRejected(RuntimeError):
    """No candidate may publish after retries are exhausted or policy blocks it."""


def generate_evaluated_candidate(
    *,
    job_id: UUID,
    branch_id: UUID,
    focal_character_id: UUID,
    storyteller: StoryDraftingAdapter,
    evaluator: EvaluatorAdapter,
    policy: ModerationAdapter,
    max_attempts: int = 3,
) -> CandidateChapter:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    for attempt in range(1, max_attempts + 1):
        candidate = CandidateChapter(
            job_id=job_id,
            branch_id=branch_id,
            focal_character_id=focal_character_id,
            screenplay=storyteller.draft(focal_character_id=focal_character_id, attempt=attempt),
        )
        policy_result = policy.assess(candidate.screenplay, PolicySubject.CANDIDATE_PROSE)
        if policy_result.decision is not PolicyDecision.ALLOW:
            raise GenerationRejected("Candidate prose was blocked by policy")
        outcome = evaluator.evaluate(candidate)
        if outcome is EvaluationOutcome.APPROVED:
            return candidate.model_copy(update={"status": CandidateStatus.APPROVED})
    raise GenerationRejected("Evaluator rejected every candidate attempt")
