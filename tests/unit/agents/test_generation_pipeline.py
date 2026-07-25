from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from story_engine.agents.context_assembler import assemble_character_context
from story_engine.agents.contracts import (
    BranchDirectorMemory,
    CharacterMemoryBuckets,
    EligibleCharacter,
)
from story_engine.domain.models import ChapterStatus
from story_engine.domain.policy_models import PolicyDecision, PolicyResult, PolicySubject
from story_engine.services.candidate_service import CandidateStagingError, commit_candidate
from story_engine.services.generation_pipeline import (
    ChapterLengthConfig,
    DiscussionNotConverged,
    DiscussionOutcome,
    EvaluationOutcome,
    GenerationRejected,
    generate_evaluated_candidate,
    run_bounded_discussion,
)


class AcceptingDirector:
    def propose_beat(
        self, *, focal_character_id: object, round_number: int, discussion: tuple[str, ...]
    ) -> str:
        return f"Beat proposal round {round_number}."


class AcceptingWorld:
    def review_beat(self, proposal: str, *, discussion: tuple[str, ...]) -> DiscussionOutcome:
        return DiscussionOutcome.ACCEPTED


class NeverAcceptingWorld:
    def review_beat(self, proposal: str, *, discussion: tuple[str, ...]) -> DiscussionOutcome:
        return DiscussionOutcome.NEEDS_REVISION


class Drafts:
    """Drafts a screenplay of roughly the requested chapter-unit length."""

    def __init__(self, words: int = 75) -> None:
        self._words = words

    def draft(self, *, focal_character_id: object, attempt: int, beat: str) -> str:
        body = " ".join(["word"] * self._words)
        return f"Attempt {attempt} ({beat}): {body}."


class Evaluator:
    def __init__(self, outcomes: list[EvaluationOutcome]) -> None:
        self.outcomes = outcomes

    def evaluate(self, candidate: object) -> EvaluationOutcome:
        return self.outcomes.pop(0)


class Allows:
    def assess(self, text: str, subject: PolicySubject) -> PolicyResult:
        return PolicyResult(decision=PolicyDecision.ALLOW, message="ok")


class Blocks:
    def assess(self, text: str, subject: PolicySubject) -> PolicyResult:
        return PolicyResult(decision=PolicyDecision.BLOCK, message="blocked")


def _character(identifier: int, score: int) -> EligibleCharacter:
    return EligibleCharacter(
        entity_id=UUID(int=identifier),
        public_summary=f"Character {identifier} is present.",
        relevance_score=score,
    )


def test_focal_character_context_feeds_the_pipeline() -> None:
    """The pipeline's focal_character_id can come straight from context assembly."""

    focal = _character(1, 100)
    context = assemble_character_context(
        branch_id=UUID(int=99),
        focal_character_id=focal.entity_id,
        branch_snapshot="A storm is rolling in.",
        eligible_characters=[focal],
        character_memories={focal.entity_id: CharacterMemoryBuckets(core=("FOCAL",))},
        director_memory=BranchDirectorMemory(),
    )

    result = generate_evaluated_candidate(
        job_id=uuid4(),
        branch_id=context.branch_id,
        focal_character_id=context.focal_character_id,
        director=AcceptingDirector(),
        world=AcceptingWorld(),
        storyteller=Drafts(),
        evaluator=Evaluator([EvaluationOutcome.APPROVED]),
        policy=Allows(),
    )

    assert result.focal_character_id == context.focal_character_id
    assert result.status.value == "APPROVED"


def test_configured_chapter_length_range_is_enforced() -> None:
    config = ChapterLengthConfig(target_seconds=30, words_per_second=2.5, tolerance=0.4)
    assert config.min_words <= 75 <= config.max_words

    with pytest.raises(GenerationRejected):
        generate_evaluated_candidate(
            job_id=uuid4(),
            branch_id=uuid4(),
            focal_character_id=uuid4(),
            director=AcceptingDirector(),
            world=AcceptingWorld(),
            storyteller=Drafts(words=3),
            evaluator=Evaluator([EvaluationOutcome.APPROVED] * 5),
            policy=Allows(),
            length_config=config,
            max_attempts=1,
        )


def test_out_of_range_length_regenerates_until_it_fits() -> None:
    config = ChapterLengthConfig(target_seconds=30, words_per_second=2.5, tolerance=0.4)

    class GrowingDrafts:
        def draft(self, *, focal_character_id: object, attempt: int, beat: str) -> str:
            words = 3 if attempt == 1 else 75
            return " ".join(["word"] * words)

    result = generate_evaluated_candidate(
        job_id=uuid4(),
        branch_id=uuid4(),
        focal_character_id=uuid4(),
        director=AcceptingDirector(),
        world=AcceptingWorld(),
        storyteller=GrowingDrafts(),
        evaluator=Evaluator([EvaluationOutcome.APPROVED]),
        policy=Allows(),
        length_config=config,
        max_attempts=3,
    )
    assert config.within_range(result.screenplay)
    assert result.status.value == "APPROVED"


def test_major_divergence_regenerates_then_approves() -> None:
    result = generate_evaluated_candidate(
        job_id=uuid4(),
        branch_id=uuid4(),
        focal_character_id=uuid4(),
        director=AcceptingDirector(),
        world=AcceptingWorld(),
        storyteller=Drafts(),
        evaluator=Evaluator([EvaluationOutcome.MAJOR_DIVERGENCE, EvaluationOutcome.APPROVED]),
        policy=Allows(),
    )
    assert result.status.value == "APPROVED"
    assert result.screenplay.startswith("Attempt 2")


def test_retries_exhaust_without_publication() -> None:
    with pytest.raises(GenerationRejected):
        generate_evaluated_candidate(
            job_id=uuid4(),
            branch_id=uuid4(),
            focal_character_id=uuid4(),
            director=AcceptingDirector(),
            world=AcceptingWorld(),
            storyteller=Drafts(),
            evaluator=Evaluator([EvaluationOutcome.MAJOR_DIVERGENCE] * 3),
            policy=Allows(),
        )


def test_policy_block_rejects_before_evaluation() -> None:
    evaluator = Evaluator([EvaluationOutcome.APPROVED])
    with pytest.raises(GenerationRejected, match="policy"):
        generate_evaluated_candidate(
            job_id=uuid4(),
            branch_id=uuid4(),
            focal_character_id=uuid4(),
            director=AcceptingDirector(),
            world=AcceptingWorld(),
            storyteller=Drafts(),
            evaluator=evaluator,
            policy=Blocks(),
        )
    # The evaluator must never even be consulted on policy-blocked prose.
    assert evaluator.outcomes == [EvaluationOutcome.APPROVED]


def test_single_character_cast_has_no_fallback_and_fails_closed() -> None:
    """With exactly one eligible/active character, a block cannot fall back to anyone else."""

    focal = _character(7, 100)
    context = assemble_character_context(
        branch_id=UUID(int=1),
        focal_character_id=focal.entity_id,
        branch_snapshot="An empty stage.",
        eligible_characters=[focal],
        character_memories={focal.entity_id: CharacterMemoryBuckets(core=("ONLY",))},
        director_memory=BranchDirectorMemory(),
    )
    assert len(context.active_cast) == 1

    with pytest.raises(GenerationRejected):
        generate_evaluated_candidate(
            job_id=uuid4(),
            branch_id=context.branch_id,
            focal_character_id=context.focal_character_id,
            director=AcceptingDirector(),
            world=AcceptingWorld(),
            storyteller=Drafts(),
            evaluator=Evaluator([EvaluationOutcome.APPROVED]),
            policy=Blocks(),
        )


def test_bounded_discussion_fails_closed_when_world_never_agrees() -> None:
    with pytest.raises(DiscussionNotConverged):
        run_bounded_discussion(
            director=AcceptingDirector(),
            world=NeverAcceptingWorld(),
            focal_character_id=uuid4(),
            max_rounds=2,
        )


def test_generation_fails_closed_when_discussion_never_converges() -> None:
    with pytest.raises(GenerationRejected):
        generate_evaluated_candidate(
            job_id=uuid4(),
            branch_id=uuid4(),
            focal_character_id=uuid4(),
            director=AcceptingDirector(),
            world=NeverAcceptingWorld(),
            storyteller=Drafts(),
            evaluator=Evaluator([EvaluationOutcome.APPROVED]),
            policy=Allows(),
            max_discussion_rounds=2,
        )


def test_illegal_starting_chapter_status_is_rejected_before_any_model_call() -> None:
    with pytest.raises(CandidateStagingError):
        generate_evaluated_candidate(
            job_id=uuid4(),
            branch_id=uuid4(),
            focal_character_id=uuid4(),
            director=AcceptingDirector(),
            world=AcceptingWorld(),
            storyteller=Drafts(),
            evaluator=Evaluator([EvaluationOutcome.APPROVED]),
            policy=Allows(),
            chapter_status=ChapterStatus.PUBLISHED,
        )


def test_no_publish_transition_is_reachable_after_an_unapproved_candidate() -> None:
    """An unapproved candidate can only ever resolve to BLOCKED, never PUBLISHED."""

    with pytest.raises(GenerationRejected):
        generate_evaluated_candidate(
            job_id=uuid4(),
            branch_id=uuid4(),
            focal_character_id=uuid4(),
            director=AcceptingDirector(),
            world=AcceptingWorld(),
            storyteller=Drafts(),
            evaluator=Evaluator([EvaluationOutcome.MAJOR_DIVERGENCE] * 3),
            policy=Allows(),
        )
    # commit_candidate itself enforces this at the state-machine level too:
    assert commit_candidate(ChapterStatus.EVALUATING, approved=False) is ChapterStatus.BLOCKED
    with pytest.raises(CandidateStagingError):
        commit_candidate(ChapterStatus.BLOCKED, approved=True)
