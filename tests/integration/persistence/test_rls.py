"""Task 2C.5 acceptance: user A cannot read/write user B's rows, a non-owner
"application" role cannot write canonical tables directly, and the
world-command SECURITY DEFINER path can still commit an allowed change.
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
    set_tenant,
)

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set; requires a live Postgres instance"
)


def test_user_a_cannot_read_or_write_user_b_rows(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user_a = create_user(cur, "rls-a@example.com")
        user_b = create_user(cur, "rls-b@example.com")
        story_b = create_story(cur, user_b, title="User B's Story")

        set_tenant(cur, user_a)
        cur.execute("SELECT id FROM stories WHERE id = %s", (story_b,))
        assert cur.fetchone() is None, "user A must not be able to read user B's story"

        cur.execute(
            "UPDATE stories SET title = 'hijacked' WHERE id = %s", (story_b,)
        )
        assert cur.rowcount == 0, "user A must not be able to write user B's story via RLS"
    conn.rollback()


def test_non_owner_role_cannot_write_canon_tables_directly_but_world_commit_function_can(
    conn: psycopg.Connection[object],
) -> None:
    # Setup (fixtures + temp role + grants) is committed on its own so it
    # survives the deliberate transaction-aborting failure checked below.
    with conn.cursor() as cur:
        user = create_user(cur, "rls-worker@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")
        entity_id = create_entity(cur, story_id, "Kaelen", branch_id)

        cur.execute("CREATE ROLE test_worker_role NOLOGIN")
        cur.execute("GRANT USAGE ON SCHEMA public TO test_worker_role")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO test_worker_role")
        cur.execute(
            "GRANT EXECUTE ON FUNCTION world_commit_entity_state(UUID, UUID, UUID, JSONB) TO test_worker_role"
        )
    conn.commit()

    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL ROLE test_worker_role")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "INSERT INTO branch_entity_states (branch_id, entity_id, state, version) "
                    "VALUES (%s, %s, '{}'::jsonb, 1)",
                    (branch_id, entity_id),
                )
        # The failed INSERT aborted this transaction; start a fresh one for
        # the positive check below.
        conn.rollback()

        with conn.cursor() as cur:
            cur.execute("SET LOCAL ROLE test_worker_role")
            cur.execute(
                "SELECT world_commit_entity_state(%s, %s, NULL, '{\"status\": \"ACTIVE\"}'::jsonb)",
                (branch_id, entity_id),
            )
            (new_state_id,) = cur.fetchone()
            assert new_state_id is not None, (
                "the SECURITY DEFINER world_commit_entity_state function must still "
                "succeed for a role with only EXECUTE, proving it is the intended "
                "narrow write path even when direct table DML is revoked"
            )
        conn.commit()
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DROP ROLE IF EXISTS test_worker_role")
        conn.commit()
