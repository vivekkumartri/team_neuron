"""OpenAI voice adapters: transcription (speech-to-text) and TTS.

Honesty note (see task.md Track K): the OpenAI Python SDK is not a
dependency of this repository at all — `OpenAIResponsesProvider` above talks
to the Responses API with plain `urllib`, and these adapters follow the same
convention rather than introducing a new SDK dependency. There is also no
bidirectional "realtime" WebSocket session to OpenAI wired up here. What is
implemented is **chunked near-real-time transcription**: the browser streams
short audio chunks (a few seconds each) over our own WebSocket, and each
chunk is transcribed with a synchronous call to OpenAI's
`POST /v1/audio/transcriptions` (Whisper) as soon as it arrives, with the
partial text pushed back immediately. This produces a live, incrementally
updating transcript, but it is a pragmatic approximation of "live streaming"
built from repeated short Whisper calls, not a single persistent bidirectional
realtime session.
"""

from __future__ import annotations

import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from story_engine.agents.provider import ModelProviderError


def _multipart_body(
    *, fields: dict[str, str], file_field: str, filename: str, file_bytes: bytes, content_type: str
) -> tuple[bytes, str]:
    boundary = f"----story-engine-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


class OpenAIVoiceProvider:
    """Server-only adapter for OpenAI's transcription and TTS REST endpoints.

    The API key is held only in process memory, never logged, never echoed
    to a client, and never embedded in a transcript/audio payload.
    """

    def __init__(self, *, api_key: str, timeout_seconds: float = 30.0) -> None:
        if not api_key:
            raise ValueError("An OpenAI API key is required")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def transcribe_chunk(
        self,
        *,
        audio_bytes: bytes,
        model: str,
        content_type: str,
        language: str | None = None,
    ) -> str:
        """Transcribe one short audio chunk via Whisper and return the text.

        This is called once per incoming chunk from the voice WebSocket, not
        once per whole utterance — that repetition is what stands in for a
        true streaming session (see module docstring).

        `language` is an optional ISO-639-1 hint (`en`/`hi`/`te` in this
        app's supported set) passed straight through to Whisper's own
        `language` parameter, which meaningfully improves transcription
        accuracy for non-English speech over letting it auto-detect. Omitted
        entirely when not provided, matching Whisper's own default.
        """

        if not audio_bytes:
            return ""
        fields = {"model": model, "response_format": "json"}
        if language:
            fields["language"] = language
        body, boundary = _multipart_body(
            fields=fields,
            file_field="file",
            filename="chunk.webm",
            file_bytes=audio_bytes,
            content_type=content_type,
        )
        request = Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                parsed = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise ModelProviderError(
                f"OpenAI transcription failed with status {error.code}"
            ) from error
        except URLError as error:
            raise ModelProviderError("OpenAI is unreachable") from error
        except TimeoutError as error:
            raise ModelProviderError("OpenAI transcription request timed out") from error
        except json.JSONDecodeError as error:
            raise ModelProviderError("OpenAI returned an invalid transcription response") from error

        text = parsed.get("text")
        return text.strip() if isinstance(text, str) else ""

    def synthesize_speech(self, *, text: str, model: str, voice: str) -> bytes:
        """Synthesize narration audio (MP3 bytes) for already-published text."""

        payload = json.dumps(
            {
                "model": model,
                "voice": voice,
                "input": text,
                "response_format": "mp3",
            }
        ).encode("utf-8")
        request = Request(
            "https://api.openai.com/v1/audio/speech",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                return bytes(response.read())
        except HTTPError as error:
            raise ModelProviderError(f"OpenAI TTS failed with status {error.code}") from error
        except URLError as error:
            raise ModelProviderError("OpenAI is unreachable") from error
        except TimeoutError as error:
            raise ModelProviderError("OpenAI TTS request timed out") from error
