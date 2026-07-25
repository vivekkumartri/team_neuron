"""Task 3F.2 acceptance: crash recovery claims a lease exactly once, and
duplicate outbox delivery never re-creates a job or double-launches it.
"""

from __future__ import annotations

import psycopg
import pytest

from story_engine.services.job_dispatcher import dispatch_pending
from story_engine.workers.outbox import write_outbox_entry
from story_engine.workers.queue import claim_next_job, release_job
from tests.integration.persistence.conftest import (
    TEST_DATABASE_URL,
    create_arc,
    create_branch,
    create_story,
    create_user,
)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set; requires a live Postgres instance"
)


def test_second_worker_recovers_an_expired_lease_exactly_once(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "queue-test@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")

        cur.execute(
            "INSERT INTO generation_jobs (branch_id, requested_by_user_id, idempotency_key, status) "
            "VALUES (%s, %s, 'lease-test', 'QUEUED') RETURNING id",
            (branch_id, user),
        )
        job_id = cur.fetchone()[0]

    # First worker claims it (a fresh QUEUED job is claimed with attempt 0,
    # not bumped, since this isn't a crash-recovery reclaim).
    first_claim = claim_next_job(conn, lease_seconds=0)
    assert first_claim is not None
    assert first_claim.id == job_id
    assert first_claim.attempt == 0

    # Simulate the lease already expiring (lease_seconds=0 above put
    # lease_expires_at at ~now(), so it's already eligible for reclaim).
    second_claim = claim_next_job(conn, lease_seconds=300)
    assert second_claim is not None
    assert second_claim.id == job_id
    assert second_claim.attempt == 1, "a reclaim must bump retry_count exactly once"

    # No third job is claimable — the lease is now live for 300s.
    assert claim_next_job(conn) is None

    release_job(conn, job_id, status="SUCCEEDED")
    conn.rollback()


class _CountingLauncher:
    def __init__(self) -> None:
        self.launched: list[str] = []

    def launch(self, *, job_key: str, job_id: object) -> None:
        self.launched.append(job_key)


def test_dispatch_is_not_repeated_for_an_already_published_outbox_entry(
    conn: psycopg.Connection[object],
) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "queue-test2@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")

    write_outbox_entry(
        conn,
        aggregate_type="generation_job",
        aggregate_id=branch_id,
        event_type="GENERATION_REQUESTED",
        payload={},
    )
    conn.commit()

    launcher = _CountingLauncher()
    first_pass = dispatch_pending(conn, launcher)
    second_pass = dispatch_pending(conn, launcher)

    assert first_pass == 1
    assert second_pass == 0, "an already-published outbox entry must not be dispatched again"
    assert launcher.launched == ["generation_job"]
    conn.rollback()


class _FailingLauncher:
    def launch(self, *, job_key: str, job_id: object) -> None:
        raise RuntimeError("Databricks Jobs API unavailable")


def test_failed_launch_leaves_the_outbox_entry_retryable(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "queue-test3@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")

    write_outbox_entry(
        conn,
        aggregate_type="generation_job",
        aggregate_id=branch_id,
        event_type="GENERATION_REQUESTED",
        payload={},
    )
    conn.commit()

    dispatched = dispatch_pending(conn, _FailingLauncher())
    assert dispatched == 0

    # It's still there for a retrying dispatcher, not silently dropped.
    dispatched_again = dispatch_pending(conn, _CountingLauncher())
    assert dispatched_again == 1
    conn.rollback()
