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


def _openai_error_summary(error: HTTPError) -> str:
    """Return a log-safe classification without exposing an upstream message."""

    error_type = "unknown"
    error_code = "unknown"
    try:
        payload = json.loads(error.read().decode("utf-8"))
        detail = payload.get("error", {})
        if isinstance(detail, dict):
            error_type = str(detail.get("type") or error_type)
            error_code = str(detail.get("code") or error_code)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return f"status={error.code}, type={error_type}, code={error_code}"


def _extract_response_text(body: dict[str, object]) -> str:
    """Extract all generated text from a raw Responses API JSON payload.

    ``output_text`` is an SDK convenience property, not a guaranteed field in
    the REST JSON response. The API returns an ``output`` array that can also
    contain reasoning and tool-call items, so inspect every message/content
    pair rather than assuming the first item is text.
    """

    convenience_text = body.get("output_text")
    if isinstance(convenience_text, str) and convenience_text.strip():
        return convenience_text.strip()

    output = body.get("output")
    if not isinstance(output, list):
        return ""

    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
    return "\n".join(text_parts)


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
            summary = _openai_error_summary(error)
            raise ModelProviderError(f"OpenAI request failed ({summary})") from error
        except URLError as error:
            raise ModelProviderError("OpenAI is unreachable") from error
        except TimeoutError as error:
            raise ModelProviderError("OpenAI request timed out") from error
        except OSError as error:
            raise ModelProviderError("OpenAI connection failed") from error
        except json.JSONDecodeError as error:
            raise ModelProviderError("OpenAI returned an invalid response") from error

        output_text = _extract_response_text(body)
        if not output_text:
            raise ModelProviderError("OpenAI returned no text output")
        return output_text
