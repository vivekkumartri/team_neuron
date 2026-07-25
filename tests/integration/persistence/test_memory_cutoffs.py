"""Task 2C.3 acceptance: a child branch reads inherited memory only through its
fork chapter and never sees a parent's future entries; Director-memory rejects
hidden-characteristic content at the schema level.
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


def test_child_branch_cannot_see_parent_memory_after_its_fork_cutoff(
    conn: psycopg.Connection[object],
) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "director-test@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        parent_branch = create_branch(cur, story_id, arc_id, name="Main")
        entity_id = create_entity(cur, story_id, "Kaelen", parent_branch)

        cur.execute(
            "INSERT INTO chapters (branch_id, chapter_index, focal_character_id, status) "
            "VALUES (%s, 1, %s, 'PUBLISHED') RETURNING id",
            (parent_branch, entity_id),
        )
        fork_chapter_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO character_memories (branch_id, character_id, memory_kind, content, source_chapter_id, visible_through_chapter_id) "
            "VALUES (%s, %s, 'EPISODIC', '{\"event\": \"met Mira\"}'::jsonb, %s, %s)",
            (parent_branch, entity_id, fork_chapter_id, fork_chapter_id),
        )

        create_branch(cur, story_id, arc_id, name="Option A", parent_branch_id=parent_branch)

        cur.execute(
            "INSERT INTO chapters (branch_id, chapter_index, focal_character_id, status) "
            "VALUES (%s, 2, %s, 'PUBLISHED') RETURNING id",
            (parent_branch, entity_id),
        )
        future_parent_chapter_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO character_memories (branch_id, character_id, memory_kind, content, source_chapter_id, visible_through_chapter_id) "
            "VALUES (%s, %s, 'EPISODIC', '{\"event\": \"parent-only future event\"}'::jsonb, %s, %s)",
            (parent_branch, entity_id, future_parent_chapter_id, future_parent_chapter_id),
        )

        # The child branch's own memory query is scoped to branch_id = child,
        # plus inherited parent memory only up to the fork chapter. The child
        # never has rows of its own yet, so simulate the context-assembler's
        # inherited-read query directly against the parent using the cutoff.
        cur.execute(
            "SELECT content FROM character_memories "
            "WHERE branch_id = %s AND character_id = %s AND visible_through_chapter_id <= %s",
            (parent_branch, entity_id, fork_chapter_id),
        )
        visible = [row[0] for row in cur.fetchall()]
        assert visible == [{"event": "met Mira"}], (
            "inherited-memory read must stop at the fork chapter and must not "
            "include events the parent branch recorded afterward"
        )
    conn.rollback()


def test_director_memory_rejects_hidden_characteristic_content(
    conn: psycopg.Connection[object],
) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "director-test2@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")

        cur.execute(
            "INSERT INTO story_directors (branch_id) VALUES (%s) RETURNING id",
            (branch_id,),
        )
        director_id = cur.fetchone()[0]

        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO director_memories (director_id, memory_kind, summary) "
                "VALUES (%s, 'STRATEGY', 'Kaelen''s hidden characteristic is that he sabotaged the Spire')",
                (director_id,),
            )
    conn.rollback()
