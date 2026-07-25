"""Ending eligibility scoring and multi-ending selection.

Closes a gap flagged in the Gap Audit v2 (finding B6): design.md set an
`ending-readiness score` threshold of 0.75 without ever defining what produces
that 0-1 number. This module is that definition — a small, explicit, weighted
function over three inputs the business/evaluator agents already produce, so
the threshold is independently checkable instead of a magic number.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MINIMUM_CHAPTERS_BEFORE_MANUAL_REQUEST = 3
ENDING_READINESS_THRESHOLD = 0.75

# Weights are configuration, not code constants that require a redeploy to
# tune — kept here as defaults matching design.md §1's limits table until an
# admin-configurable override is wired up in Task 4G.2's settings endpoint.
_CHAPTER_COUNT_WEIGHT = 0.35
_BUSINESS_PACING_WEIGHT = 0.40
_OPEN_THREAD_RESOLUTION_WEIGHT = 0.25

# A branch is considered to have "enough" chapters once it reaches double the
# manual-request floor; beyond that, additional chapters no longer increase
# this sub-score (a long-running branch isn't automatically "more ready").
_CHAPTER_COUNT_SATURATION = MINIMUM_CHAPTERS_BEFORE_MANUAL_REQUEST * 2


class EndingReadinessInputs(BaseModel):
    model_config = ConfigDict(frozen=True)

    published_chapter_count: int = Field(ge=0)
    # Business agent's own 0-100 pacing sub-score (design.md's
    # `business_report_breakdown` "Pacing" row), normalized to 0-1 here.
    business_pacing_score: int = Field(ge=0, le=100)
    # Fraction of the branch Director's `open_threads` memory rows marked
    # resolved rather than still-open, as of the latest chapter.
    open_thread_resolution_ratio: float = Field(ge=0.0, le=1.0)


def compute_ending_readiness_score(inputs: EndingReadinessInputs) -> float:
    chapter_count_score = min(inputs.published_chapter_count / _CHAPTER_COUNT_SATURATION, 1.0)
    business_pacing_score = inputs.business_pacing_score / 100
    return round(
        chapter_count_score * _CHAPTER_COUNT_WEIGHT
        + business_pacing_score * _BUSINESS_PACING_WEIGHT
        + inputs.open_thread_resolution_ratio * _OPEN_THREAD_RESOLUTION_WEIGHT,
        4,
    )


def is_ending_eligible(inputs: EndingReadinessInputs) -> bool:
    return compute_ending_readiness_score(inputs) >= ENDING_READINESS_THRESHOLD


def manual_ending_request_allowed(published_chapter_count: int) -> bool:
    """The author may always request ending options once the minimum chapter
    count is reached, independent of the automatic readiness score.
    """

    return published_chapter_count >= MINIMUM_CHAPTERS_BEFORE_MANUAL_REQUEST
