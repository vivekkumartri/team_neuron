"""Reuse the persistence-suite fixtures for the security test suite.

Same skip-without-`TEST_DATABASE_URL` behavior as
`tests/integration/persistence/conftest.py` — these tests are collected but
skipped in the plain `pytest -q` unit run.
"""

from __future__ import annotations

from tests.integration.persistence.conftest import (  # noqa: F401
    _migrated_template_db,
    conn,
    create_arc,
    create_branch,
    create_entity,
    create_story,
    create_user,
    set_tenant,
)
