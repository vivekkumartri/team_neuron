"""Track 2 acceptance: canon-event-request replay and the branch-state ETag.

Auth-boundary/schema-shape only here (no live DB in this sandbox) — the
actual replay-returns-same-row behavior is exercised once a real Postgres
instance is available, same pattern as the rest of tests/contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from story_engine.api.routes.world import (
    BranchStateResponse,
    _check_if_match,
    _etag_for,
    _fetch_branch_state,
)
from story_engine.app import create_app

client = TestClient(create_app())

BRANCH_ID = UUID("00000000-0000-0000-0000-000000000000")


def test_canon_event_request_with_idempotency_key_requires_auth() -> None:
    response = client.post(
        "/api/v1/branches/00000000-0000-0000-0000-000000000000/canon-event-requests",
        headers={"Idempotency-Key": "test-key-1"},
        json={"event_type": "INTRODUCE_ENTITY"},
    )
    assert response.status_code == 401


def test_canon_event_request_with_if_match_requires_auth() -> None:
    """The If-Match precondition check happens inside the authenticated

    handler body, so an unauthenticated caller is still rejected with 401
    before any ETag comparison occurs — auth is checked first regardless of
    which optional headers are present.
    """

    response = client.post(
        "/api/v1/branches/00000000-0000-0000-0000-000000000000/canon-event-requests",
        headers={"If-Match": 'W/"deadbeef"'},
        json={"event_type": "INTRODUCE_ENTITY"},
    )
    assert response.status_code == 401


def test_branch_state_requires_auth() -> None:
    response = client.get("/api/v1/branches/00000000-0000-0000-0000-000000000000/state")
    assert response.status_code == 401


def _empty_state_connection() -> MagicMock:
    """A fake connection whose cursor returns no entity/relationship rows,

    so `_fetch_branch_state` produces a deterministic, empty
    `BranchStateResponse` for a given branch id — enough to unit-test the
    ETag comparison logic in `_check_if_match` without a live Postgres.
    """

    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    return connection


def test_if_match_absent_allows_write_unconditionally() -> None:
    connection = _empty_state_connection()
    _check_if_match(connection, BRANCH_ID, None)  # no exception


def test_if_match_matching_etag_allows_write() -> None:
    connection = _empty_state_connection()
    current = _fetch_branch_state(connection, BRANCH_ID)
    matching_etag = _etag_for(current)
    _check_if_match(connection, BRANCH_ID, matching_etag)  # no exception


def test_if_match_stale_etag_rejected_with_412() -> None:
    connection = _empty_state_connection()
    with pytest.raises(HTTPException) as excinfo:
        _check_if_match(connection, BRANCH_ID, 'W/"stale-not-the-real-hash"')
    assert excinfo.value.status_code == 412


def test_if_match_wildcard_allows_write() -> None:
    connection = _empty_state_connection()
    _check_if_match(connection, BRANCH_ID, "*")  # no exception


def test_branch_state_response_etag_is_deterministic() -> None:
    """Sanity check that `_etag_for` is a pure function of the payload's

    content, matching the docstring's "weak content hash" contract — the
    same `BranchStateResponse` must always produce the same ETag so a
    client's If-Match header from an earlier GET remains comparable.
    """

    result = BranchStateResponse(branch_id=BRANCH_ID, entities=[], relationships=[])
    assert _etag_for(result) == _etag_for(result)
