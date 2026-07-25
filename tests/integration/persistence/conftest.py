"""Shared fixtures for Lakebase persistence integration tests.

These tests run against a real Postgres instance (a local Postgres or a
provisioned Lakebase `dev` branch) supplied via `TEST_DATABASE_URL`. They are
skipped automatically when that variable is absent so `pytest -q` (the unit
suite) never requires a live database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import UUID

import psycopg
import pytest

from scripts.migrate import apply_migrations

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set; persistence integration tests require a live Postgres instance",
)


@pytest.fixture(scope="session")
def _migrated_template_db() -> Iterator[str]:
    """Apply all migrations once per test session, then reuse the schema."""

    assert TEST_DATABASE_URL
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        applied_first = apply_migrations(connection)
        # Task 2C.1 acceptance: a second application is a no-op, not an error.
        applied_second = apply_migrations(connection)
        assert applied_second == [], (
            "migration runner must be idempotent on a second run; "
            f"unexpectedly re-applied {applied_second!r} (first run applied {applied_first!r})"
        )
    yield TEST_DATABASE_URL


@pytest.fixture
def conn(_migrated_template_db: str) -> Iterator[psycopg.Connection[object]]:
    """One transaction-scoped connection per test; rolled back afterward."""

    connection = psycopg.connect(_migrated_template_db)
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def create_user(cursor: psycopg.Cursor[object], email: str) -> UUID:
    cursor.execute(
        "INSERT INTO users (databricks_user_id, email) VALUES (%s, %s) RETURNING id",
        (f"dbx-{email}", email),
    )
    return cursor.fetchone()[0]


def create_story(cursor: psycopg.Cursor[object], user_id: UUID, title: str = "Test Story") -> UUID:
    cursor.execute(
        "INSERT INTO stories (user_id, title) VALUES (%s, %s) RETURNING id",
        (user_id, title),
    )
    return cursor.fetchone()[0]


def create_arc(cursor: psycopg.Cursor[object], story_id: UUID, name: str = "Arc 1") -> UUID:
    cursor.execute(
        "INSERT INTO arcs (story_id, name) VALUES (%s, %s) RETURNING id",
        (story_id, name),
    )
    return cursor.fetchone()[0]


def create_branch(
    cursor: psycopg.Cursor[object],
    story_id: UUID,
    arc_id: UUID,
    name: str = "Main",
    parent_branch_id: UUID | None = None,
) -> UUID:
    cursor.execute(
        "INSERT INTO branches (story_id, arc_id, parent_branch_id, name, status) "
        "VALUES (%s, %s, %s, %s, 'ACTIVE') RETURNING id",
        (story_id, arc_id, parent_branch_id, name),
    )
    return cursor.fetchone()[0]


def create_entity(cursor: psycopg.Cursor[object], story_id: UUID, name: str, founding_branch_id: UUID) -> UUID:
    cursor.execute(
        "INSERT INTO entities (story_id, name, entity_type, founding_branch_id) "
        "VALUES (%s, %s, 'character', %s) RETURNING id",
        (story_id, name, founding_branch_id),
    )
    return cursor.fetchone()[0]


def set_tenant(cursor: psycopg.Cursor[object], user_id: UUID) -> None:
    cursor.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
