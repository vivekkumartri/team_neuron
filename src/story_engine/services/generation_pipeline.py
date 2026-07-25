"""Bounded, evaluator-gated generation orchestration.

Pure, provider-and-worker-agnostic orchestration logic for one chapter-unit
generation attempt:

1. A bounded Director/World discussion agrees on one beat before any prose
   is drafted (a beat proposal that World never accepts within
   `max_discussion_rounds` fails closed rather than looping forever).
2. The Storyteller drafts a candidate screenplay for that beat, sized to a
   configurable ~30-second chapter unit (`ChapterLengthConfig`).
3. The candidate is staged (visibly unpublished — see `candidate_service`)
   and must pass the content-policy gate *before* evaluation, per spec.
4. The Evaluator's outcome either approves the candidate or triggers
   automatic regeneration (a fresh discussion + draft) after a major
   divergence, up to `max_attempts`.
5. Only an APPROVED outcome is allowed to reach `commit_candidate(...,
   approved=True)`; anything else resolves to BLOCKED, never PUBLISHED.

`story_engine.workers.generation_job` is today's real, working end-to-end
OpenAI-backed loop; it does not yet call into this module (see task.md
Task 3E.3 status for why). This module is independently unit-testable with
fake adapters, matching the pattern in `tests/unit/agents/test_adapters.py`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from story_engine.domain.models import ChapterStatus
from story_engine.domain.policy_models import PolicyDecision, PolicySubject
from story_engine.security.content_policy import ModerationAdapter
from story_engine.services.candidate_service import (
    CandidateChapter,
    CandidateStatus,
    commit_candidate,
    stage_candidate_for_evaluation,
)

__all__ = [
    "CandidateChapter",
    "CandidateStatus",
    "ChapterLengthConfig",
    "DirectorAdapter",
    "DiscussionOutcome",
    "DiscussionNotConverged",
    "EvaluationOutcome",
    "EvaluatorAdapter",
    "GenerationRejected",
    "StoryDraftingAdapter",
    "WorldAdapter",
    "generate_evaluated_candidate",
    "run_bounded_discussion",
]


class EvaluationOutcome(StrEnum):
    APPROVED = "APPROVED"
    MINOR_DIVERGENCE = "MINOR_DIVERGENCE"
    MAJOR_DIVERGENCE = "MAJOR_DIVERGENCE"


class DiscussionOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    NEEDS_REVISION = "NEEDS_REVISION"


class ChapterLengthConfig(BaseModel):
    """Configurable ~N-second chapter unit expressed as a word-count window."""

    model_config = ConfigDict(frozen=True)

    target_seconds: float = Field(default=30.0, gt=0)
    words_per_second: float = Field(default=2.5, gt=0)
    tolerance: float = Field(default=0.4, ge=0, lt=1)

    @property
    def target_words(self) -> int:
        return max(1, round(self.target_seconds * self.words_per_second))

    @property
    def min_words(self) -> int:
        return max(1, round(self.target_words * (1 - self.tolerance)))

    @property
    def max_words(self) -> int:
        return round(self.target_words * (1 + self.tolerance))

    def within_range(self, screenplay: str) -> bool:
        word_count = len(screenplay.split())
        return self.min_words <= word_count <= self.max_words


class StoryDraftingAdapter(Protocol):
    def draft(self, *, focal_character_id: UUID, attempt: int, beat: str) -> str: ...


class EvaluatorAdapter(Protocol):
    def evaluate(self, candidate: CandidateChapter) -> EvaluationOutcome: ...


class DirectorAdapter(Protocol):
    def propose_beat(
        self, *, focal_character_id: UUID, round_number: int, discussion: tuple[str, ...]
    ) -> str: ...


class WorldAdapter(Protocol):
    def review_beat(self, proposal: str, *, discussion: tuple[str, ...]) -> DiscussionOutcome: ...


class GenerationRejected(RuntimeError):
    """No candidate may publish after retries are exhausted or policy blocks it."""


class DiscussionNotConverged(GenerationRejected):
    """Director and World failed to agree on a beat within the round budget."""


def run_bounded_discussion(
    *,
    director: DirectorAdapter,
    world: WorldAdapter,
    focal_character_id: UUID,
    max_rounds: int = 3,
) -> tuple[str, tuple[str, ...]]:
    """Bound the Director/World back-and-forth so it cannot loop indefinitely.

    Returns the accepted beat proposal and the full transcript. Raises
    `DiscussionNotConverged` if World never accepts within `max_rounds`.
    """

    if max_rounds < 1:
        raise ValueError("max_rounds must be at least one")
    transcript: list[str] = []
    for round_number in range(1, max_rounds + 1):
        proposal = director.propose_beat(
            focal_character_id=focal_character_id,
            round_number=round_number,
            discussion=tuple(transcript),
        )
        transcript.append(f"director: {proposal}")
        outcome = world.review_beat(proposal, discussion=tuple(transcript))
        transcript.append(f"world: {outcome.value}")
        if outcome is DiscussionOutcome.ACCEPTED:
            return proposal, tuple(transcript)
    raise DiscussionNotConverged("Director and World did not reach continuity agreement")


def generate_evaluated_candidate(
    *,
    job_id: UUID,
    branch_id: UUID,
    focal_character_id: UUID,
    director: DirectorAdapter,
    world: WorldAdapter,
    storyteller: StoryDraftingAdapter,
    evaluator: EvaluatorAdapter,
    policy: ModerationAdapter,
    max_attempts: int = 3,
    max_discussion_rounds: int = 3,
    length_config: ChapterLengthConfig | None = None,
    chapter_status: ChapterStatus = ChapterStatus.GENERATING,
) -> CandidateChapter:
    """Run one bounded discussion -> draft -> policy -> evaluate -> commit cycle.

    A fresh Director/World discussion (and a fresh draft) happens on every
    attempt, so "automatic regeneration after major divergence" always
    re-derives the beat rather than repeating a rejected one verbatim.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    length_config = length_config or ChapterLengthConfig()

    # Validate (without mutating) that this chapter is actually eligible to
    # move into evaluation before any model calls are made.
    stage_candidate_for_evaluation(chapter_status)

    last_candidate: CandidateChapter | None = None
    for attempt in range(1, max_attempts + 1):
        beat, _transcript = run_bounded_discussion(
            director=director,
            world=world,
            focal_character_id=focal_character_id,
            max_rounds=max_discussion_rounds,
        )
        screenplay = storyteller.draft(
            focal_character_id=focal_character_id, attempt=attempt, beat=beat
        )
        candidate = CandidateChapter(
            job_id=job_id,
            branch_id=branch_id,
            focal_character_id=focal_character_id,
            screenplay=screenplay,
        )
        last_candidate = candidate

        policy_result = policy.assess(candidate.screenplay, PolicySubject.CANDIDATE_PROSE)
        if policy_result.decision is not PolicyDecision.ALLOW:
            commit_candidate(ChapterStatus.EVALUATING, approved=False)
            raise GenerationRejected("Candidate prose was blocked by policy")

        if not length_config.within_range(candidate.screenplay):
            # Out-of-window length is treated as a divergence: regenerate
            # rather than evaluate a candidate that doesn't fit the
            # configured chapter-unit duration.
            continue

        outcome = evaluator.evaluate(candidate)
        if outcome is EvaluationOutcome.APPROVED:
            commit_candidate(ChapterStatus.EVALUATING, approved=True)
            return candidate.model_copy(update={"status": CandidateStatus.APPROVED})

    commit_candidate(ChapterStatus.EVALUATING, approved=False)
    del last_candidate  # never returned/published; retained only for future debugging hooks
    raise GenerationRejected("Evaluator rejected every candidate attempt")
