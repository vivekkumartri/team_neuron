"""Client for the local IndicF5 zero-shot TTS server (`indicf5_tts/api_server.py`).

This is a plain HTTP adapter, matching the style of `agents/voice_provider.py`'s
`OpenAIVoiceProvider`: no SDK dependency, `urllib` only, errors normalized to
`ModelProviderError` so callers don't need to know which backend failed.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from story_engine.agents.provider import ModelProviderError


class IndicF5Provider:
    """Server-only adapter for the self-hosted IndicF5 `/generate` endpoint.

    Reference-voice cloning inputs (`ref_audio_base64` + `ref_text`) are
    always sent explicitly by the caller — this adapter never guesses or
    falls back to the upstream server's own bundled default voice, so a
    caller always knows exactly which reference clip produced each line.
    """

    def __init__(self, *, base_url: str, timeout_seconds: float = 120.0) -> None:
        if not base_url:
            raise ValueError("An IndicF5 server base_url is required")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def synthesize_speech(
        self,
        *,
        text: str,
        ref_audio_base64: str,
        ref_text: str,
        nfe_step: int = 32,
        speed: float = 1.0,
    ) -> bytes:
        payload = json.dumps(
            {
                "text": text,
                "ref_audio_base64": ref_audio_base64,
                "ref_text": ref_text,
                "nfe_step": nfe_step,
                "speed": speed,
            }
        ).encode("utf-8")
        request = Request(
            f"{self._base_url}/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                return bytes(response.read())
        except HTTPError as error:
            detail = ""
            try:
                detail = json.loads(error.read().decode("utf-8")).get("detail", "")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass
            raise ModelProviderError(
                f"IndicF5 TTS failed with status {error.code}" + (f": {detail}" if detail else "")
            ) from error
        except URLError as error:
            raise ModelProviderError("IndicF5 server is unreachable") from error
        except TimeoutError as error:
            raise ModelProviderError("IndicF5 TTS request timed out") from error
