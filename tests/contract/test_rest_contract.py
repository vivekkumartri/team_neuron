"""Contract-level checks that don't require a live Lakebase connection.

Full authenticated round-trips (JIT provisioning idempotency, cross-tenant
404s, idempotent replay) are exercised in `tests/integration/persistence`
against a real database; this module covers what's checkable from the
OpenAPI schema and the auth boundary alone, so it runs in the plain `pytest -q`
unit job without needing `TEST_DATABASE_URL`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from story_engine.app import create_app

client = TestClient(create_app())


def test_missing_identity_headers_return_401() -> None:
    response = client.get("/api/v1/stories")
    assert response.status_code == 401


def test_health_endpoint_does_not_require_auth() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_has_no_hidden_characteristic_field() -> None:
    schema = client.get("/openapi.json").json()
    serialized = str(schema).lower()
    for forbidden in ("hidden_characteristic", "hidden characteristic", "secret exists"):
        assert forbidden not in serialized, (
            f"OpenAPI schema must never expose a {forbidden!r}-shaped field; "
            "hidden characteristics do not have an author-facing API surface (design.md §5)"
        )


def test_chapter_response_never_exposes_candidate_staging_fields() -> None:
    schema = client.get("/openapi.json").json()
    chapter_schema = schema["components"]["schemas"]["ChapterResponse"]["properties"]
    # The published-chapter DTO must only ever contain published fields —
    # never a "candidate"/"staged"/"draft" field that could leak unapproved
    # content (design.md "Loophole and Integrity Guards").
    for forbidden in ("candidate", "staged", "draft_content"):
        assert forbidden not in chapter_schema, f"ChapterResponse must not expose {forbidden!r}"


def test_canon_event_request_requires_auth() -> None:
    response = client.post(
        "/api/v1/branches/00000000-0000-0000-0000-000000000000/canon-event-requests",
        json={"event_type": "INTRODUCE_ENTITY"},
    )
    assert response.status_code == 401


def test_canon_event_request_schema_rejects_unknown_fields() -> None:
    schema = client.get("/openapi.json").json()
    request_schema = schema["components"]["schemas"]["CanonEventRequestInput"]
    assert request_schema.get("additionalProperties") is False, (
        "CanonEventRequestInput must forbid unknown fields (extra='forbid')"
    )


def test_ending_options_require_auth() -> None:
    response = client.get("/api/v1/branches/00000000-0000-0000-0000-000000000000/ending-options")
    assert response.status_code == 401


def test_revision_request_requires_auth() -> None:
    response = client.post(
        "/api/v1/chapters/00000000-0000-0000-0000-000000000000/revisions",
        json={"author_patch": "Change the ending line."},
    )
    assert response.status_code == 401


def test_revision_request_schema_rejects_unknown_fields() -> None:
    schema = client.get("/openapi.json").json()
    request_schema = schema["components"]["schemas"]["RevisionRequestInput"]
    assert request_schema.get("additionalProperties") is False
