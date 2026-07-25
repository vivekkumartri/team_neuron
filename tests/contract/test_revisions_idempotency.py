"""Track 3 acceptance: revision-request replay via Idempotency-Key."""

from __future__ import annotations

from fastapi.testclient import TestClient

from story_engine.app import create_app

client = TestClient(create_app())


def test_revision_request_with_idempotency_key_requires_auth() -> None:
    response = client.post(
        "/api/v1/chapters/00000000-0000-0000-0000-000000000000/revisions",
        headers={"Idempotency-Key": "revise-1"},
        json={"author_patch": "Make the ending gentler."},
    )
    assert response.status_code == 401


def test_revision_list_requires_auth() -> None:
    response = client.get("/api/v1/chapters/00000000-0000-0000-0000-000000000000/revisions")
    assert response.status_code == 401
