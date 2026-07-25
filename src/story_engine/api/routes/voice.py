"""Live-ish speech-to-text over a WebSocket.

## Auth boundary tradeoff

Every other route in this API uses `authenticate_request` as a normal
FastAPI `Depends`, which reads the `x-forwarded-user`/`x-forwarded-email`
headers that the Databricks Apps reverse proxy injects on every HTTP
request. A WebSocket handshake is still an HTTP request (the `Upgrade`
request), so those same headers are present and readable via
`websocket.headers` — there is no need for a query-param token or a
first-message handshake, and no extra credential material has to be pushed
into browser JS or the URL (which would otherwise leak into proxy/access
logs). This is the simplest-and-correct option for this deployment: it holds
only as long as the reverse proxy is the sole path to this app (true today;
if this endpoint is ever exposed behind something that does not enforce that
header, it must gain an explicit token handshake instead).

## What "streaming" means here

There is no bidirectional realtime session to OpenAI. The browser sends
short binary audio chunks; each chunk is transcribed synchronously via
`OpenAIVoiceProvider.transcribe_chunk` (Whisper) as it arrives, and the
resulting text is pushed back as a `partial` transcript event. When the
client sends the `"stop"` control message (or disconnects), the concatenation
of all chunk transcripts is re-validated as a whole and pushed back as one
`final` event. See `agents/voice_provider.py` for the fuller honesty note.

## Content-policy gate

The `final` transcript is exactly the text a caller would otherwise type
into a free-text field, so before it is emitted as `final` it is run through
`RuleBasedContentPolicy.assess` (`security/content_policy.py`) — the same
gate typed input goes through downstream in seed/trait/canon-event/revision
services. If the gate blocks or redirects, the WebSocket emits a `rejected`
event carrying the safe-alternative message instead of a `final` transcript,
so a rejected voice utterance can never reach an agent or DB write any more
than typed text could.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from story_engine.agents.voice_provider import OpenAIVoiceProvider
from story_engine.api.settings import load_settings
from story_engine.domain.policy_models import PolicyDecision, PolicySubject
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.security.content_policy import RuleBasedContentPolicy

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

_MAX_CHUNK_BYTES = 2_000_000
_MAX_UTTERANCE_CHARS = 8_000


def _authenticate_websocket(websocket: WebSocket) -> tuple[str, str] | None:
    """Mirror `authenticate_request`'s header contract for a WS handshake."""

    databricks_user_id = websocket.headers.get("x-forwarded-user")
    email = websocket.headers.get("x-forwarded-email")
    if not databricks_user_id or not email:
        return None
    return databricks_user_id, email


def _provision_user(databricks_user_id: str, email: str) -> None:
    settings = load_settings()
    with lakebase_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT app_provision_user(%s, %s)", (databricks_user_id, email))
        connection.commit()


_SUPPORTED_LANGUAGE_HINTS = {"en", "hi", "te"}


def _language_hint(websocket: WebSocket) -> str | None:
    """Optional ISO-639-1 hint (`en`/`hi`/`te`) forwarded to Whisper.

    This is the story's `language` preference (task.md Phase 6 multilingual
    entry), passed by the client as a `?language=` query param — the query
    string, not a header, since `voice-stream.ts` already builds the WS URL
    from `window.location` and appending a query param there is the natural
    place to carry a caller-known-but-not-identity value (identity itself
    still comes from headers only, per this module's auth boundary above).
    An absent or unrecognized value means "no hint" — Whisper auto-detects
    the language rather than being forced into a wrong one.
    """

    raw = websocket.query_params.get("language")
    if raw and raw.lower() in _SUPPORTED_LANGUAGE_HINTS:
        return raw.lower()
    return None


@router.websocket("/transcribe")
async def transcribe(websocket: WebSocket) -> None:
    identity = _authenticate_websocket(websocket)
    if identity is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    databricks_user_id, email = identity
    settings = load_settings()
    if not settings.llm_configured:
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    try:
        _provision_user(databricks_user_id, email)
    except Exception:  # noqa: BLE001 - never leak provisioning internals to the client
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    await websocket.accept()
    provider = OpenAIVoiceProvider(api_key=settings.openai_api_key or "")
    policy = RuleBasedContentPolicy()
    chunk_transcripts: list[str] = []
    language_hint = _language_hint(websocket)

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"] is not None:
                audio_bytes = message["bytes"]
                if len(audio_bytes) > _MAX_CHUNK_BYTES:
                    await websocket.send_json(
                        {"type": "error", "message": "Audio chunk too large."}
                    )
                    continue
                try:
                    partial_text = provider.transcribe_chunk(
                        audio_bytes=audio_bytes,
                        model=settings.openai_transcription_model,
                        content_type="audio/webm",
                        language=language_hint,
                    )
                except Exception:  # noqa: BLE001 - surface a safe message only
                    await websocket.send_json(
                        {"type": "error", "message": "Transcription is temporarily unavailable."}
                    )
                    continue
                if partial_text:
                    chunk_transcripts.append(partial_text)
                    await websocket.send_json({"type": "partial", "text": partial_text})
                continue

            if "text" in message and message["text"] is not None:
                control = _parse_control(message["text"])
                if control == "stop":
                    await _emit_final(websocket, chunk_transcripts, policy)
                    chunk_transcripts = []
                continue
    except WebSocketDisconnect:
        return


def _parse_control(raw: str) -> str | None:
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip().lower() or None
    if isinstance(payload, dict):
        action = payload.get("action")
        return str(action).lower() if action is not None else None
    return None


async def _emit_final(
    websocket: WebSocket, chunk_transcripts: list[str], policy: RuleBasedContentPolicy
) -> None:
    full_text = " ".join(part for part in chunk_transcripts if part).strip()
    if not full_text:
        await websocket.send_json({"type": "final", "text": ""})
        return
    full_text = full_text[:_MAX_UTTERANCE_CHARS]

    result = policy.assess(full_text, PolicySubject.CLARIFICATION)
    if result.decision != PolicyDecision.ALLOW:
        await websocket.send_json(
            {
                "type": "rejected",
                "message": result.message,
                "safe_alternative": result.safe_alternative,
            }
        )
        return
    await websocket.send_json({"type": "final", "text": full_text})
