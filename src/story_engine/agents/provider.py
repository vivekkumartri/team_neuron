"""Small model-provider abstraction and the OpenAI Responses implementation."""

from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelProvider(Protocol):
    def complete(self, *, system_prompt: str, user_data: str, model: str) -> str: ...


class ModelProviderError(RuntimeError):
    """Safe error surfaced when a model provider is unavailable or rejects a request."""


class OpenAIResponsesProvider:
    """Synchronous, server-only OpenAI Responses API adapter.

    The caller passes distinct trusted instructions and untrusted story data.
    The API key is held only in process memory and never included in a model
    prompt, event payload, exception message, or browser response.
    """

    def __init__(self, *, api_key: str, timeout_seconds: float = 90.0) -> None:
        if not api_key:
            raise ValueError("An OpenAI API key is required")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def complete(self, *, system_prompt: str, user_data: str, model: str) -> str:
        payload = json.dumps(
            {
                "model": model,
                "instructions": system_prompt,
                "input": user_data,
            }
        ).encode("utf-8")
        request = Request(
            "https://api.openai.com/v1/responses",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise ModelProviderError(f"OpenAI request failed with status {error.code}") from error
        except URLError as error:
            raise ModelProviderError("OpenAI is unreachable") from error
        except TimeoutError as error:
            raise ModelProviderError("OpenAI request timed out") from error
        except json.JSONDecodeError as error:
            raise ModelProviderError("OpenAI returned an invalid response") from error

        output_text = body.get("output_text")
        if not isinstance(output_text, str) or not output_text.strip():
            raise ModelProviderError("OpenAI returned no text output")
        return output_text.strip()
