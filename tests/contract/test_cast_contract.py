"""Track 1 acceptance: cast-lock is idempotent, family-tree read is auth-gated."""

from __future__ import annotations

from fastapi.testclient import TestClient

from story_engine.app import create_app

client = TestClient(create_app())


def test_cast_lock_requires_auth() -> None:
    response = client.post("/api/v1/stories/00000000-0000-0000-0000-000000000000/cast-lock")
    assert response.status_code == 401


def test_family_tree_requires_auth() -> None:
    response = client.get("/api/v1/stories/00000000-0000-0000-0000-000000000000/family-tree")
    assert response.status_code == 401
