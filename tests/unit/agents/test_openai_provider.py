from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from story_engine.agents.provider import ModelProviderError, OpenAIResponsesProvider


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_openai_responses_provider_sends_instructions_and_returns_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urlopen = MagicMock(return_value=_Response({"output_text": "A real scene."}))
    monkeypatch.setattr("story_engine.agents.provider.urlopen", urlopen)
    provider = OpenAIResponsesProvider(api_key="test-key")

    result = provider.complete(system_prompt="trusted", user_data="untrusted", model="test-model")

    assert result == "A real scene."
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.openai.com/v1/responses"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert json.loads(request.data) == {
        "model": "test-model",
        "instructions": "trusted",
        "input": "untrusted",
    }


def test_openai_responses_provider_fails_closed_for_missing_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "story_engine.agents.provider.urlopen", lambda *_args, **_kwargs: _Response({})
    )
    provider = OpenAIResponsesProvider(api_key="test-key")

    with pytest.raises(ModelProviderError, match="no text output"):
        provider.complete(system_prompt="trusted", user_data="untrusted", model="test-model")
