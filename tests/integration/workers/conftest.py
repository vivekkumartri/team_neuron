"""Reuse the persistence-suite fixtures for worker-queue integration tests."""

from __future__ import annotations

from tests.integration.persistence.conftest import (  # noqa: F401
    _migrated_template_db,
    conn,
    create_arc,
    create_branch,
    create_story,
    create_user,
)
