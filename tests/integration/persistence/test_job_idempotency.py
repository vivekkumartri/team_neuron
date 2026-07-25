"""Task 2C.4 acceptance: idempotency-key replay returns the same job, a second
active job on a branch is rejected, and candidate rows are not visible through
published-chapter queries.
"""

from __future__ import annotations

import psycopg
import pytest

from tests.integration.persistence.conftest import (
    TEST_DATABASE_URL,
    create_arc,
    create_branch,
    create_entity,
    create_story,
    create_user,
)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set; requires a live Postgres instance"
)


def test_idempotency_key_replay_returns_same_job(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "job-test@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")

        cur.execute(
            "INSERT INTO generation_jobs (branch_id, requested_by_user_id, idempotency_key, status) "
            "VALUES (%s, %s, 'req-1', 'QUEUED') "
            "ON CONFLICT (requested_by_user_id, idempotency_key) DO UPDATE SET status = generation_jobs.status "
            "RETURNING id",
            (branch_id, user),
        )
        first_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO generation_jobs (branch_id, requested_by_user_id, idempotency_key, status) "
            "VALUES (%s, %s, 'req-1', 'QUEUED') "
            "ON CONFLICT (requested_by_user_id, idempotency_key) DO UPDATE SET status = generation_jobs.status "
            "RETURNING id",
            (branch_id, user),
        )
        second_id = cur.fetchone()[0]

        assert first_id == second_id, "replaying the same idempotency key must return the original job"
    conn.rollback()


def test_second_active_job_on_same_branch_is_rejected(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "job-test2@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")

        cur.execute(
            "INSERT INTO generation_jobs (branch_id, requested_by_user_id, idempotency_key, status) "
            "VALUES (%s, %s, 'req-a', 'QUEUED')",
            (branch_id, user),
        )

        with pytest.raises(psycopg.errors.UniqueViolation):
            cur.execute(
                "INSERT INTO generation_jobs (branch_id, requested_by_user_id, idempotency_key, status) "
                "VALUES (%s, %s, 'req-b', 'QUEUED')",
                (branch_id, user),
            )
    conn.rollback()


def test_candidate_rows_are_not_visible_through_published_chapter_queries(
    conn: psycopg.Connection[object],
) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "job-test3@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")
        entity_id = create_entity(cur, story_id, "Kaelen", branch_id)

        cur.execute(
            "INSERT INTO generation_jobs (branch_id, requested_by_user_id, idempotency_key, status) "
            "VALUES (%s, %s, 'req-c', 'RUNNING') RETURNING id",
            (branch_id, user),
        )
        job_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO candidate_chapters (job_id, branch_id, focal_character_id, screenplay, status) "
            "VALUES (%s, %s, %s, '{\"scenes\": []}'::jsonb, 'REJECTED')",
            (job_id, branch_id, entity_id),
        )

        # `chapters` is the only table read by published-chapter queries;
        # candidate_chapters is a distinct staging table, so a rejected
        # candidate is structurally unreachable from it.
        cur.execute("SELECT count(*) FROM chapters WHERE branch_id = %s", (branch_id,))
        (published_count,) = cur.fetchone()
        assert published_count == 0, "a rejected candidate must never appear as a published chapter row"
    conn.rollback()
