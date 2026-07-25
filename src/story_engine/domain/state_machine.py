"""State transition rules enforced before persistence."""

from __future__ import annotations

from collections.abc import Mapping

from story_engine.domain.models import ChapterStatus


class InvalidStateTransition(ValueError):
    """Raised when a caller attempts to mutate immutable published history."""


ALLOWED_CHAPTER_TRANSITIONS: Mapping[ChapterStatus, frozenset[ChapterStatus]] = {
    ChapterStatus.DRAFT: frozenset({ChapterStatus.QUEUED, ChapterStatus.ARCHIVED}),
    ChapterStatus.QUEUED: frozenset(
        {ChapterStatus.GENERATING, ChapterStatus.FAILED, ChapterStatus.ARCHIVED}
    ),
    ChapterStatus.GENERATING: frozenset(
        {ChapterStatus.EVALUATING, ChapterStatus.FAILED, ChapterStatus.BLOCKED}
    ),
    ChapterStatus.EVALUATING: frozenset(
        {
            ChapterStatus.PUBLISHED,
            ChapterStatus.GENERATING,
            ChapterStatus.FAILED,
            ChapterStatus.BLOCKED,
        }
    ),
    ChapterStatus.PUBLISHED: frozenset({ChapterStatus.ARCHIVED}),
    ChapterStatus.BLOCKED: frozenset({ChapterStatus.QUEUED, ChapterStatus.ARCHIVED}),
    ChapterStatus.FAILED: frozenset({ChapterStatus.QUEUED, ChapterStatus.ARCHIVED}),
    ChapterStatus.ARCHIVED: frozenset(),
}


def ensure_chapter_transition(current: ChapterStatus, target: ChapterStatus) -> None:
    """Validate a one-way chapter lifecycle transition."""

    if target not in ALLOWED_CHAPTER_TRANSITIONS[current]:
        raise InvalidStateTransition(f"Chapter cannot transition from {current} to {target}")
