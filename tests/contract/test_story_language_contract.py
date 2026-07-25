"""Contract checks for the new `language` field on story creation.

Task.md Phase 6 multilingual entry: `language` is a per-story preference
chosen once at creation time, restricted to `en`/`hi`/`te` via the
`StoryLanguage` enum. `create_story` requires a live Lakebase connection
(via `tenant_connection`), and the auth dependency itself needs a DB round
trip too, so a full `POST /api/v1/stories` round trip with a real 201/422
distinction can't be exercised in this sandbox (see the module docstring in
`test_rest_contract.py` for the general pattern this file follows) — in
fact, without identity headers the auth dependency raises 401 *before* the
body is validated at all (verified empirically), so a route-level 422
assertion here would be dishonest. What *is* verified without a database is
that `StoryInput`, the exact Pydantic model `create_story` uses, accepts
`en`/`hi`/`te` and rejects anything else (e.g. `fr`) at the model-validation
layer — the same validation FastAPI runs against a request body before a
route function ever executes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from story_engine.api.routes.stories import StoryInput
from story_engine.app import create_app
from story_engine.domain.models import StoryLanguage

client = TestClient(create_app())


@pytest.mark.parametrize("language", ["en", "hi", "te"])
def test_story_input_accepts_supported_languages(language: str) -> None:
    payload = StoryInput(title="A lighthouse keeper's ledger", language=language)
    assert payload.language == StoryLanguage(language)


def test_story_input_defaults_to_english_when_language_omitted() -> None:
    payload = StoryInput(title="A lighthouse keeper's ledger")
    assert payload.language == StoryLanguage.ENGLISH


@pytest.mark.parametrize("language", ["fr", "es", "EN ", "hindi", ""])
def test_story_input_rejects_unsupported_language_codes(language: str) -> None:
    with pytest.raises(ValidationError):
        StoryInput(title="A lighthouse keeper's ledger", language=language)


def test_story_creation_still_requires_auth_regardless_of_language_value() -> None:
    # Documents the precedence finding above: the auth boundary is checked
    # for every route the same way regardless of this new field, so a
    # missing-identity request is rejected the same way it always was.
    response = client.post(
        "/api/v1/stories", json={"title": "A lighthouse keeper's ledger", "language": "hi"}
    )
    assert response.status_code == 401


def test_story_input_accepts_a_full_edited_cast() -> None:
    # Task.md Task 4H.2 gap closure: `POST /stories` now accepts the full
    # author-edited cast array from `CastLock.tsx` instead of only ever
    # creating one hardcoded "Protagonist" entity.
    payload = StoryInput(
        title="A rogue watchmaker's secret",
        language="en",
        cast=[
            {
                "name": "Kaelen",
                "role": "Protagonist · Rogue Watchmaker",
                "voice": "Terse, dry humor",
                "traits": "Cautious, loyal",
                "visual": "Grease-stained hands",
                "is_protagonist": True,
            },
            {
                "name": "Mira Voss",
                "role": "Guild Enforcer",
                "voice": "Clipped",
                "traits": "Rule-bound",
                "visual": "Brass mask",
                "is_protagonist": False,
            },
        ],
    )
    assert len(payload.cast) == 2
    assert payload.cast[0].is_protagonist is True
    # No `hidden` field exists on the model at all (task.md 0.4): passing one
    # is rejected outright by `extra="forbid"`.


def test_story_input_defaults_to_empty_cast_when_omitted() -> None:
    payload = StoryInput(title="A lighthouse keeper's ledger", language="en")
    assert payload.cast == []


def test_story_input_rejects_a_hidden_field_on_a_cast_member() -> None:
    with pytest.raises(ValidationError):
        StoryInput(
            title="A rogue watchmaker's secret",
            language="en",
            cast=[
                {
                    "name": "Kaelen",
                    "role": "Protagonist",
                    "voice": "",
                    "traits": "",
                    "visual": "",
                    "hidden": "a dark secret",
                }
            ],
        )


def test_story_input_rejects_more_than_six_cast_members() -> None:
    seven_members = [
        {"name": f"Character {i}", "role": "Supporting", "is_protagonist": i == 0}
        for i in range(7)
    ]
    with pytest.raises(ValidationError):
        StoryInput(title="A crowded cast", language="en", cast=seven_members)
