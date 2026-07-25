"""Task 5J.1: tenant-crossing negative tests for the tables added in this

pass (Task 4G.2's `canon_event_requests`) — `tests/integration/persistence/test_rls.py`
already covers `stories`/`branch_entity_states`/the SECURITY DEFINER write
path; this file extends that coverage to the newer canon-event surface
rather than duplicating it.
"""

from __future__ import annotations

import psycopg
import pytest

from tests.integration.persistence.conftest import TEST_DATABASE_URL
from tests.security.conftest import create_arc, create_branch, create_story, create_user, set_tenant

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set; RLS negative tests require a live Postgres instance",
)


def test_user_a_cannot_read_user_b_canon_event_requests(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user_a = create_user(cur, "canon-a@example.com")
        user_b = create_user(cur, "canon-b@example.com")
        story_b = create_story(cur, user_b, title="User B's Story")
        arc_b = create_arc(cur, story_b)
        branch_b = create_branch(cur, story_b, arc_b)

        set_tenant(cur, user_b)
        cur.execute(
            "INSERT INTO canon_event_requests "
            "(branch_id, requested_by_user_id, event_type, proposed_payload, status) "
            "VALUES (%s, %s, 'INTRODUCE_ENTITY', '{}'::jsonb, 'DRAFT') RETURNING id",
            (branch_b, user_b),
        )
        request_id = cur.fetchone()[0]

        set_tenant(cur, user_a)
        cur.execute("SELECT id FROM canon_event_requests WHERE id = %s", (request_id,))
        assert cur.fetchone() is None, (
            "user A must not be able to read user B's canon_event_requests row"
        )
    conn.rollback()
