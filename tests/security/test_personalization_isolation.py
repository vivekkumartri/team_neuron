"""Task 5J.1: unauthorized personalization-snapshot use.

A user's `user_preferences` and `personalization_snapshots` rows must never
be readable by another user, even though both tables are keyed only by
`user_id` with no story/branch join to lean on.
"""

from __future__ import annotations

import psycopg
import pytest

from tests.integration.persistence.conftest import TEST_DATABASE_URL
from tests.security.conftest import create_user, set_tenant

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set; personalization isolation tests require a live Postgres instance",
)


def test_user_a_cannot_read_user_b_preferences(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user_a = create_user(cur, "pref-a@example.com")
        user_b = create_user(cur, "pref-b@example.com")

        set_tenant(cur, user_b)
        cur.execute(
            "INSERT INTO user_preferences (user_id, preference_key, preference_value, source, consented_at) "
            "VALUES (%s, 'tone', '\"hopeful\"'::jsonb, 'EXPLICIT', now()) RETURNING id",
            (user_b,),
        )
        preference_id = cur.fetchone()[0]

        set_tenant(cur, user_a)
        cur.execute("SELECT id FROM user_preferences WHERE id = %s", (preference_id,))
        assert cur.fetchone() is None, "user A must not be able to read user B's preference row"
    conn.rollback()


def test_user_a_cannot_read_user_b_personalization_snapshot(
    conn: psycopg.Connection[object],
) -> None:
    with conn.cursor() as cur:
        user_a = create_user(cur, "snap-a@example.com")
        user_b = create_user(cur, "snap-b@example.com")

        set_tenant(cur, user_b)
        cur.execute(
            "INSERT INTO personalization_snapshots (user_id, snapshot_version, preferences) "
            "VALUES (%s, 1, '{}'::jsonb) RETURNING id",
            (user_b,),
        )
        snapshot_id = cur.fetchone()[0]

        set_tenant(cur, user_a)
        cur.execute("SELECT id FROM personalization_snapshots WHERE id = %s", (snapshot_id,))
        assert cur.fetchone() is None, (
            "user A must not be able to read user B's personalization snapshot"
        )
    conn.rollback()
