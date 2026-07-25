from __future__ import annotations

import pytest

from story_engine.domain.models import ChapterStatus
from story_engine.domain.state_machine import InvalidStateTransition, ensure_chapter_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ChapterStatus.DRAFT, ChapterStatus.QUEUED),
        (ChapterStatus.QUEUED, ChapterStatus.GENERATING),
        (ChapterStatus.GENERATING, ChapterStatus.EVALUATING),
        (ChapterStatus.EVALUATING, ChapterStatus.PUBLISHED),
        (ChapterStatus.EVALUATING, ChapterStatus.GENERATING),
        (ChapterStatus.BLOCKED, ChapterStatus.QUEUED),
        (ChapterStatus.PUBLISHED, ChapterStatus.ARCHIVED),
    ],
)
def test_allowed_transition(current: ChapterStatus, target: ChapterStatus) -> None:
    ensure_chapter_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ChapterStatus.PUBLISHED, ChapterStatus.GENERATING),
        (ChapterStatus.PUBLISHED, ChapterStatus.DRAFT),
        (ChapterStatus.ARCHIVED, ChapterStatus.QUEUED),
        (ChapterStatus.QUEUED, ChapterStatus.PUBLISHED),
    ],
)
def test_illegal_transition_is_rejected(current: ChapterStatus, target: ChapterStatus) -> None:
    with pytest.raises(InvalidStateTransition):
        ensure_chapter_transition(current, target)

