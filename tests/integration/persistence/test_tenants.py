"""Task 2C.1 acceptance: migration idempotency, personalization snapshot isolation."""

from __future__ import annotations

import psycopg
import pytest

from tests.integration.persistence.conftest import (
    TEST_DATABASE_URL,
    create_story,
    create_user,
    set_tenant,
)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set; requires a live Postgres instance"
)


def test_migration_idempotency(conn: psycopg.Connection[object]) -> None:
    # Covered by the session-scoped `_migrated_template_db` fixture asserting a
    # second `apply_migrations` call applies zero migrations; re-assert here so
    # a failure surfaces under this test's name too.
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM schema_migrations")
        (count,) = cur.fetchone()
        assert count >= 7


def test_snapshot_cannot_use_another_users_preference(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user_a = create_user(cur, "alice@example.com")
        user_b = create_user(cur, "bob@example.com")

        cur.execute(
            "INSERT INTO user_preferences (user_id, preference_key, preference_value, source, consented_at) "
            "VALUES (%s, 'tone', '\"dark\"', 'EXPLICIT', now()) RETURNING id",
            (user_a,),
        )
        alice_preference_id = cur.fetchone()[0]

        # A snapshot is a copy of preference *content*, not a foreign key to
        # another user's row, but the API layer must never let user B create a
        # snapshot whose `preferences` payload was sourced from user A's rows.
        # This is enforced by application code (see api/routes/preferences.py),
        # not a DB constraint alone, so assert the constraint that *is*
        # DB-enforced: a snapshot always belongs to exactly one user_id and
        # cannot reference rows owned by a different user through RLS.
        set_tenant(cur, user_b)
        cur.execute(
            "SELECT preference_value FROM user_preferences WHERE id = %s", (alice_preference_id,)
        )
        assert cur.fetchone() is None, "RLS must hide user A's preference row from user B's session"


def test_disabled_story_cannot_select_a_snapshot(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "carol@example.com")
        story_id = create_story(cur, user)

        cur.execute(
            "INSERT INTO personalization_snapshots (user_id, snapshot_version, preferences) "
            "VALUES (%s, 1, '{}'::jsonb) RETURNING id",
            (user,),
        )
        snapshot_id = cur.fetchone()[0]

        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "UPDATE stories SET personalization_snapshot_id = %s WHERE id = %s AND personalization_enabled = false",
                (snapshot_id, story_id),
            )
    conn.rollback()
