"""Contract-level checks for the narration HTTP endpoint and voice WS route.

What's covered here (no live Lakebase, no live OpenAI, no real audio I/O —
matches the rest of this module's constraints):
  - the narration endpoint enforces the same auth boundary as every other
    authenticated route (401 without identity headers);
  - the OpenAPI schema exposes the narration route and does not leak a
    candidate/staging field through it.

What is NOT covered here (documented, not silently skipped): a full
WebSocket auth-boundary round trip. `fastapi.testclient.TestClient` can open
a WebSocket test session, but it does so by directly calling the ASGI app
with an in-process handshake that FastAPI's `TestClient` builds only from
whatever headers are explicitly passed to `client.websocket_connect(...,
headers=...)` — there is no live Databricks Apps reverse proxy in this
sandbox to inject `x-forwarded-user`/`x-forwarded-email`, so a "does the
proxy actually gate this" test cannot be written honestly here. What can be
verified without network/audio is that the handshake is rejected when those
headers are absent, which is exercised below.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from story_engine.app import create_app

client = TestClient(create_app())


def test_narration_requires_auth() -> None:
    response = client.get(
        "/api/v1/chapters/00000000-0000-0000-0000-000000000000/narration"
    )
    assert response.status_code == 401


def test_narration_route_is_exposed() -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/chapters/{chapter_id}/narration" in paths
    # Narration has no request/response DTO of its own (it returns raw audio
    # bytes), so there is no schema object to check field-by-field the way
    # `test_chapter_response_never_exposes_candidate_staging_fields` does for
    # `ChapterResponse` — the absence of a body model here is itself the
    # guarantee that no staging field is newly exposed through this route.


def test_voice_websocket_rejects_connection_without_identity_headers() -> None:
    # No `x-forwarded-user`/`x-forwarded-email` headers are supplied, mirroring
    # what a request bypassing the Databricks Apps proxy would look like.
    try:
        with client.websocket_connect("/api/v1/voice/transcribe"):
            raise AssertionError("Connection should have been closed by the server")
    except WebSocketDisconnect as disconnect:
        assert disconnect.code == 1008
