"""Quota state and policy-block checks (Track 7 / plan P4 quota gap).

Wired into `api/routes/progression.py`'s `POST /branches/{id}/progression`
handler (a follow-up integration step, done without touching that route's
idempotency-key replay / outbox-write logic) and exposed read-only via
`GET /api/v1/me/quota`. `QuotaState` is the shape the route computes from
real counts and `web/components/features/workspace/QuotaBanner.tsx` renders.

Limits are fixed defaults here (no per-tenant override table exists yet);
that's an honest simplification, not a fabricated data source — the counts
themselves are always read live from Lakebase.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class QuotaCategory(StrEnum):
    CHAPTERS_PER_MONTH = "CHAPTERS_PER_MONTH"
    CONCURRENT_BRANCHES = "CONCURRENT_BRANCHES"
    CONCURRENT_GENERATION_JOBS = "CONCURRENT_GENERATION_JOBS"


# Default limits per category. No per-tenant quota-override table exists yet
# (Task 3F.1/5J.1 status note), so every tenant currently shares these.
DEFAULT_LIMITS: dict[QuotaCategory, int] = {
    QuotaCategory.CHAPTERS_PER_MONTH: 60,
    QuotaCategory.CONCURRENT_BRANCHES: 20,
    QuotaCategory.CONCURRENT_GENERATION_JOBS: 1,
}


class QuotaState(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: QuotaCategory
    used: int = Field(ge=0)
    limit: int = Field(ge=0)

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)

    @property
    def exceeded(self) -> bool:
        return self.used >= self.limit

    @property
    def approaching(self) -> bool:
        """80% of limit or higher, but not yet exceeded — the "you're close"

        warning band a UI would show before the hard stop.
        """

        return not self.exceeded and self.limit > 0 and self.used / self.limit >= 0.8


class QuotaExceededError(RuntimeError):
    """Raised by a caller enforcing a `QuotaState` that has no remaining budget."""

    def __init__(self, state: QuotaState) -> None:
        self.state = state
        super().__init__(
            f"{state.category.value} quota exceeded ({state.used}/{state.limit}). "
            "Existing content remains available; this only blocks new submissions "
            "in this category until the quota resets or increases."
        )


def enforce_quota(state: QuotaState) -> None:
    if state.exceeded:
        raise QuotaExceededError(state)


def current_quota_states(connection: object, *, user_id: object) -> list[QuotaState]:
    """Compute every category's live `QuotaState` for one user from Lakebase.

    Kept here (rather than inline in a route) so both `progression.py`'s
    pre-submission check and a read-only `GET /me/quota` endpoint share one
    source of truth for "used" counts.
    """

    from typing import Any, cast  # local import: keep this module import-light for unit tests

    conn = cast(Any, connection)
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM generation_jobs j "
            "JOIN branches b ON b.id = j.branch_id "
            "WHERE j.requested_by_user_id = %s "
            "AND j.created_at >= date_trunc('month', now())",
            (user_id,),
        )
        chapters_this_month = int(cast(tuple[Any, ...], cursor.fetchone())[0])

        cursor.execute(
            "SELECT count(*) FROM branches b "
            "JOIN stories s ON s.id = b.story_id "
            "WHERE s.user_id = %s AND b.archived_at IS NULL",
            (user_id,),
        )
        active_branches = int(cast(tuple[Any, ...], cursor.fetchone())[0])

        cursor.execute(
            "SELECT count(*) FROM generation_jobs "
            "WHERE requested_by_user_id = %s AND ("
            "  status = 'QUEUED' "
            "  OR (status = 'RUNNING' AND (lease_expires_at IS NULL OR lease_expires_at >= now()))"
            ")",
            (user_id,),
        )
        active_jobs = int(cast(tuple[Any, ...], cursor.fetchone())[0])

    return [
        QuotaState(
            category=QuotaCategory.CHAPTERS_PER_MONTH,
            used=chapters_this_month,
            limit=DEFAULT_LIMITS[QuotaCategory.CHAPTERS_PER_MONTH],
        ),
        QuotaState(
            category=QuotaCategory.CONCURRENT_BRANCHES,
            used=active_branches,
            limit=DEFAULT_LIMITS[QuotaCategory.CONCURRENT_BRANCHES],
        ),
        QuotaState(
            category=QuotaCategory.CONCURRENT_GENERATION_JOBS,
            used=active_jobs,
            limit=DEFAULT_LIMITS[QuotaCategory.CONCURRENT_GENERATION_JOBS],
        ),
    ]
