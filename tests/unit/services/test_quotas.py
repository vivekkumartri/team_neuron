from __future__ import annotations

import pytest

from story_engine.services.quotas import (
    QuotaCategory,
    QuotaExceededError,
    QuotaState,
    enforce_quota,
)


def test_remaining_and_exceeded() -> None:
    state = QuotaState(category=QuotaCategory.CHAPTERS_PER_MONTH, used=5, limit=10)
    assert state.remaining == 5
    assert not state.exceeded
    assert not state.approaching


def test_approaching_band() -> None:
    state = QuotaState(category=QuotaCategory.CHAPTERS_PER_MONTH, used=8, limit=10)
    assert state.approaching
    assert not state.exceeded


def test_exceeded_state() -> None:
    state = QuotaState(category=QuotaCategory.CONCURRENT_BRANCHES, used=10, limit=10)
    assert state.exceeded
    assert state.remaining == 0
    assert not state.approaching


def test_enforce_quota_raises_with_user_facing_message() -> None:
    state = QuotaState(category=QuotaCategory.CONCURRENT_GENERATION_JOBS, used=3, limit=3)
    with pytest.raises(QuotaExceededError) as excinfo:
        enforce_quota(state)
    assert "existing content remains available" in str(excinfo.value).lower()


def test_enforce_quota_passes_when_under_limit() -> None:
    enforce_quota(QuotaState(category=QuotaCategory.CHAPTERS_PER_MONTH, used=1, limit=10))
