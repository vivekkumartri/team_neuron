"""Task 2C.2 acceptance: forking a branch never mutates the parent/sibling, and
a historical chapter resolves the trait-state version that was current when it
was generated, even after later branches supersede it.
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


def test_fork_does_not_mutate_parent_or_sibling(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "author@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        parent_branch = create_branch(cur, story_id, arc_id, name="Main")
        entity_id = create_entity(cur, story_id, "Kaelen", parent_branch)

        cur.execute(
            "INSERT INTO branch_entity_states (branch_id, entity_id, state, version) "
            "VALUES (%s, %s, '{\"status\": \"ACTIVE\"}'::jsonb, 1)",
            (parent_branch, entity_id),
        )
        cur.execute(
            "INSERT INTO character_trait_states (branch_id, character_id, traits, version) "
            "VALUES (%s, %s, '{\"traits\": \"cautious\"}'::jsonb, 1)",
            (parent_branch, entity_id),
        )

        child_branch = create_branch(cur, story_id, arc_id, name="Option A", parent_branch_id=parent_branch)

        # Child diverges: entity dies, traits change.
        cur.execute(
            "INSERT INTO branch_entity_states (branch_id, entity_id, state, version) "
            "VALUES (%s, %s, '{\"status\": \"DECEASED\"}'::jsonb, 1)",
            (child_branch, entity_id),
        )
        cur.execute(
            "INSERT INTO character_trait_states (branch_id, character_id, traits, version) "
            "VALUES (%s, %s, '{\"traits\": \"reckless\"}'::jsonb, 2)",
            (child_branch, entity_id),
        )

        cur.execute(
            "SELECT state FROM branch_entity_states WHERE branch_id = %s AND entity_id = %s AND is_current",
            (parent_branch, entity_id),
        )
        (parent_state,) = cur.fetchone()
        assert parent_state["status"] == "ACTIVE", "child-branch write leaked into the parent branch"

        cur.execute(
            "SELECT traits FROM character_trait_states WHERE branch_id = %s AND character_id = %s ORDER BY version DESC LIMIT 1",
            (parent_branch, entity_id),
        )
        (parent_traits,) = cur.fetchone()
        assert parent_traits["traits"] == "cautious", "child-branch trait edit leaked into the parent branch"
    conn.rollback()


def test_historical_chapter_resolves_its_original_trait_version(conn: psycopg.Connection[object]) -> None:
    with conn.cursor() as cur:
        user = create_user(cur, "author2@example.com")
        story_id = create_story(cur, user)
        arc_id = create_arc(cur, story_id)
        branch_id = create_branch(cur, story_id, arc_id, name="Main")
        entity_id = create_entity(cur, story_id, "Mira", branch_id)

        cur.execute(
            "INSERT INTO character_trait_states (branch_id, character_id, traits, version) "
            "VALUES (%s, %s, '{\"traits\": \"clipped, procedural\"}'::jsonb, 1) RETURNING id",
            (branch_id, entity_id),
        )
        trait_v1 = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO chapters (branch_id, chapter_index, focal_character_id, focal_trait_state_id, status) "
            "VALUES (%s, 1, %s, %s, 'PUBLISHED') RETURNING id",
            (branch_id, entity_id, trait_v1),
        )
        chapter_id = cur.fetchone()[0]

        # A later trait edit supersedes v1 for future generation, but must not
        # rewrite what Chapter 1 says it was generated from.
        cur.execute(
            "INSERT INTO character_trait_states (branch_id, character_id, traits, version) "
            "VALUES (%s, %s, '{\"traits\": \"softened, open\"}'::jsonb, 2)",
            (branch_id, entity_id),
        )

        cur.execute(
            "SELECT cts.traits FROM chapters c "
            "JOIN character_trait_states cts ON cts.id = c.focal_trait_state_id "
            "WHERE c.id = %s",
            (chapter_id,),
        )
        (resolved_traits,) = cur.fetchone()
        assert resolved_traits["traits"] == "clipped, procedural", (
            "rewinding to a published chapter must resolve the trait-state version "
            "recorded at generation time, not the branch's current version"
        )
    conn.rollback()
