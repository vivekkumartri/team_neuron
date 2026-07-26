"""Contract tests for `POST /stories/cast-proposal` (task.md Task 4H.2 gap
closure — an LLM-driven cast proposal wired into the real cast-setup UI).

No live Lakebase and no live OpenAI network access in this sandbox, matching
every other contract test in this module (see `test_voice_contract.py`).
Auth is asserted the normal way (401 without identity headers); for the
authenticated paths, the `authenticate_request` dependency is overridden so
these tests never need a real database connection, and the model provider
is stubbed so no real network call is attempted.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from story_engine.agents.provider import ModelProviderError
from story_engine.api.auth import AuthenticatedUser, authenticate_request
from story_engine.api.settings import RuntimeSettings
from story_engine.app import create_app

app = create_app()
client = TestClient(app)

_FAKE_USER = AuthenticatedUser(id=uuid4(), databricks_user_id="u-1", email="author@example.com")


def _override_auth() -> AuthenticatedUser:
    return _FAKE_USER


@pytest.fixture(autouse=True)
def _auth_override():
    app.dependency_overrides[authenticate_request] = _override_auth
    yield
    app.dependency_overrides.pop(authenticate_request, None)


def test_cast_proposal_requires_auth() -> None:
    app.dependency_overrides.pop(authenticate_request, None)
    response = client.post(
        "/api/v1/stories/cast-proposal", json={"seed": "A lighthouse keeper.", "language": "en"}
    )
    assert response.status_code == 401
    app.dependency_overrides[authenticate_request] = _override_auth


def test_cast_proposal_blocks_policy_violation_before_calling_the_model(monkeypatch) -> None:
    class _ExplodingProvider:
        def __init__(self, *, api_key: str) -> None:
            raise AssertionError("Provider must never be constructed for a blocked seed")

    monkeypatch.setattr(
        "story_engine.api.routes.stories.load_settings",
        lambda: RuntimeSettings(openai_api_key="test-key"),
    )
    monkeypatch.setattr(
        "story_engine.api.routes.stories.OpenAIResponsesProvider", _ExplodingProvider
    )

    response = client.post(
        "/api/v1/stories/cast-proposal",
        json={"seed": "A story with explicit sex scenes throughout.", "language": "en"},
    )

    assert response.status_code == 422


def test_cast_proposal_returns_llm_generated_cast_when_allowed(monkeypatch) -> None:
    class _StubProvider:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-key"

        def complete(self, *, system_prompt: str, user_data: str, model: str) -> str:
            del system_prompt, user_data, model
            return (
                '[{"name": "Kaelen", "role": "Protagonist · Rogue Watchmaker", '
                '"voice": "Terse, dry", "traits": "Cautious, loyal", '
                '"visual": "Grease-stained hands"},'
                '{"name": "Mira", "role": "Guild Enforcer", "voice": "Clipped", '
                '"traits": "Rule-bound", "visual": "Brass mask"}]'
            )

    monkeypatch.setattr(
        "story_engine.api.routes.stories.load_settings",
        lambda: RuntimeSettings(openai_api_key="test-key"),
    )
    monkeypatch.setattr("story_engine.api.routes.stories.OpenAIResponsesProvider", _StubProvider)

    response = client.post(
        "/api/v1/stories/cast-proposal",
        json={"seed": "A rogue watchmaker hides a secret in a clocktower city.", "language": "en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["characters"]) == 2
    assert body["characters"][0]["name"] == "Kaelen"
    assert "Protagonist" in body["characters"][0]["role"]
    assert body["source"] == "llm"
    # No hidden/secret field is ever present (task.md 0.4 — the prototype's
    # blurred hidden-characteristic row is explicitly not ported).
    assert "hidden" not in body["characters"][0]


def test_cast_proposal_returns_503_when_llm_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        "story_engine.api.routes.stories.load_settings",
        lambda: RuntimeSettings(openai_api_key=None),
    )
    response = client.post(
        "/api/v1/stories/cast-proposal", json={"seed": "A lighthouse keeper.", "language": "en"}
    )
    assert response.status_code == 503


def test_cast_proposal_returns_seed_fallback_when_provider_fails(monkeypatch) -> None:
    class _FailingProvider:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-key"

        def complete(self, *, system_prompt: str, user_data: str, model: str) -> str:
            del system_prompt, user_data, model
            raise ModelProviderError("provider unavailable")

    monkeypatch.setattr(
        "story_engine.api.routes.stories.load_settings",
        lambda: RuntimeSettings(openai_api_key="test-key"),
    )
    monkeypatch.setattr("story_engine.api.routes.stories.OpenAIResponsesProvider", _FailingProvider)

    response = client.post(
        "/api/v1/stories/cast-proposal",
        json={"seed": "i am on moon with my 2 friends rahul and teja", "language": "hi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "seed_fallback"
    assert [character["name"] for character in body["characters"]] == ["You", "Rahul", "Teja"]
