"""In-memory candidate contract, plus state-machine-respecting staging/commit helpers.

`CandidateChapter` is the pure data contract shared with `generation_pipeline`.
The functions below decide *whether* a chapter-status transition is legal (via
`story_engine.domain.state_machine`) so a candidate can never be treated as
published without first passing through EVALUATING and an explicit approved
commit. This module has no DB access, matching the other `services/` modules
(`progression.py`, `trait_states.py`, `canon_events.py`) — persistence
adapters (e.g. `workers/generation_job.py`) own the actual row writes and the
`world_publish_generated_candidate` call.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from story_engine.domain.models import ChapterStatus
from story_engine.domain.state_machine import ensure_chapter_transition


class CandidateStatus(StrEnum):
    """Status of an individual candidate screenplay, distinct from `ChapterStatus`.

    A candidate is always `STAGED` (visibly unpublished) until an evaluator
    outcome resolves it to `APPROVED`, `REJECTED` (eligible for automatic
    regeneration), or `BLOCKED` (policy gate or retries exhausted).
    """

    STAGED = "STAGED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class CandidateChapter(BaseModel):
    """A drafted-but-not-yet-committed chapter unit for one focal character."""

    model_config = ConfigDict(frozen=True)

    job_id: UUID
    branch_id: UUID
    focal_character_id: UUID
    screenplay: str = Field(min_length=1, max_length=12_000)
    status: CandidateStatus = CandidateStatus.STAGED


class CandidateStagingError(ValueError):
    """A candidate cannot be staged or committed from its current chapter status."""


def stage_candidate_for_evaluation(current: ChapterStatus) -> ChapterStatus:
    """Move a chapter from active generation into pre-publication evaluation.

    Staging never publishes anything: the only legal destination here is
    EVALUATING. A candidate produced at this point must remain unpublished —
    no scene or canon row exists yet — until `commit_candidate` is called
    with an APPROVED outcome.
    """

    try:
        ensure_chapter_transition(current, ChapterStatus.EVALUATING)
    except ValueError as exc:
        raise CandidateStagingError(str(exc)) from exc
    return ChapterStatus.EVALUATING


def commit_candidate(current: ChapterStatus, *, approved: bool) -> ChapterStatus:
    """Finalize a staged candidate: PUBLISHED only if the evaluator approved it.

    A rejected/blocked candidate transitions to BLOCKED, never PUBLISHED, so
    an unapproved candidate can never produce a published scene or canon row.
    """

    target = ChapterStatus.PUBLISHED if approved else ChapterStatus.BLOCKED
    try:
        ensure_chapter_transition(current, target)
    except ValueError as exc:
        raise CandidateStagingError(str(exc)) from exc
    return target
