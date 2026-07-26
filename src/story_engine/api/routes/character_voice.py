"""Multi-voice ("voice agent") character audio: one IndicF5 voice per speaker.

Accepts either a published chapter (reusing `services/narration.py`'s
published-only read, same as `routes/narration.py`) or raw pasted script text
(same free-text posture as the WS transcript in `routes/voice.py` — gated
through `RuleBasedContentPolicy` before it ever reaches an LLM or the TTS
backend, since it is caller-supplied untrusted text either way).
"""

from __future__ import annotations

import base64
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from story_engine.agents.indicf5_provider import IndicF5Provider
from story_engine.agents.provider import ModelProviderError, OpenAIResponsesProvider
from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.api.settings import RuntimeSettings, load_settings
from story_engine.domain.policy_models import PolicyDecision, PolicySubject
from story_engine.security.content_policy import RuleBasedContentPolicy
from story_engine.services.character_audio import CharacterAudioError, synthesize_script_audio
from story_engine.services.narration import published_chapter_text
from story_engine.services.narration_jobs import (
    ESTIMATED_SECONDS,
    NarrationJob,
    NarrationStatus,
    get_status,
    start_job,
)
from story_engine.services.voice_casting import VoiceCastingError
from story_engine.services.voice_uploads import (
    VoiceUploadError,
    delete_character_voice,
    list_character_voices,
    save_character_voice,
)

router = APIRouter(prefix="/api/v1/voice", tags=["character-voice"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]

# Keep well under both the LLM casting call's practical prompt size and a
# single IndicF5 request's practical synthesis time for a prototype.
_MAX_SCRIPT_CHARS = 12_000


class ScriptAudioRequest(BaseModel):
    script_text: str = Field(min_length=1, max_length=_MAX_SCRIPT_CHARS)


class CharacterAudioLineResponse(BaseModel):
    scene_index: int
    kind: str
    speaker: str | None
    text: str
    voice_id: str
    audio_base64: str


class CharacterAudioResponse(BaseModel):
    lines: list[CharacterAudioLineResponse]


class NarrationStatusResponse(BaseModel):
    status: NarrationStatus
    estimated_seconds: int | None = None
    error: str | None = None
    lines: list[CharacterAudioLineResponse] | None = None


class CharacterVoiceResponse(BaseModel):
    character_name: str
    content_type: str


class CharacterVoiceListResponse(BaseModel):
    voices: list[CharacterVoiceResponse]


def _require_configured() -> RuntimeSettings:
    settings = load_settings()
    if not settings.llm_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice casting is not configured in this environment",
        )
    if not settings.indicf5_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Character audio synthesis is not configured in this environment",
        )
    return settings


def _synthesize_and_respond(
    raw_text: str, settings: RuntimeSettings, user: AuthenticatedUser
) -> CharacterAudioResponse:
    provider = OpenAIResponsesProvider(api_key=settings.openai_api_key or "")
    tts = IndicF5Provider(base_url=settings.indicf5_base_url or "")
    overrides = list_character_voices(str(user.id))

    try:
        lines = synthesize_script_audio(
            raw_text=raw_text,
            provider=provider,
            casting_model=settings.openai_model,
            tts=tts,
            voice_overrides=overrides,
        )
    except CharacterAudioError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except VoiceCastingError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except ModelProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Character audio synthesis failed"
        ) from error

    return CharacterAudioResponse(
        lines=[
            CharacterAudioLineResponse(
                scene_index=line.scene_index,
                kind=line.kind.value,
                speaker=line.speaker,
                text=line.text,
                voice_id=line.voice_id,
                audio_base64=base64.b64encode(line.audio_bytes).decode("ascii"),
            )
            for line in lines
        ]
    )


@router.post("/script-audio")
def generate_script_audio(
    body: ScriptAudioRequest, user: CurrentUser
) -> CharacterAudioResponse:
    settings = _require_configured()

    policy = RuleBasedContentPolicy()
    result = policy.assess(body.script_text, PolicySubject.CLARIFICATION)
    if result.decision != PolicyDecision.ALLOW:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.message)

    return _synthesize_and_respond(body.script_text, settings, user)


def _narration_response(job: NarrationJob) -> NarrationStatusResponse:
    return NarrationStatusResponse(
        status=job.status,
        estimated_seconds=ESTIMATED_SECONDS if job.status == NarrationStatus.GENERATING else None,
        error=job.error,
        lines=(
            [
                CharacterAudioLineResponse(
                    scene_index=line.scene_index,
                    kind=line.kind.value,
                    speaker=line.speaker,
                    text=line.text,
                    voice_id=line.voice_id,
                    audio_base64=base64.b64encode(line.audio_bytes).decode("ascii"),
                )
                for line in job.lines
            ]
            if job.status == NarrationStatus.READY
            else None
        ),
    )


@router.post("/chapters/{chapter_id}/narration")
def start_chapter_narration(chapter_id: UUID, user: CurrentUser) -> NarrationStatusResponse:
    """Start (or return the already-running/finished) narration job for a chapter.

    Generation runs on a background thread rather than inline in this
    request — a whole chapter's worth of IndicF5 zero-shot lines realistically
    takes minutes, well past what an HTTP request should block on. Calling
    this again while a job is already `generating`/`ready` for this chapter
    is a no-op that just returns the existing job's status.
    """

    settings = _require_configured()

    with tenant_connection(user) as connection:
        text = published_chapter_text(connection, chapter_id)

    provider = OpenAIResponsesProvider(api_key=settings.openai_api_key or "")
    tts = IndicF5Provider(base_url=settings.indicf5_base_url or "")
    overrides = list_character_voices(str(user.id))

    job = start_job(
        chapter_id=chapter_id,
        raw_text=text,
        provider=provider,
        casting_model=settings.openai_model,
        tts=tts,
        voice_overrides=overrides,
    )
    return _narration_response(job)


@router.get("/chapters/{chapter_id}/narration")
def get_chapter_narration(chapter_id: UUID, user: CurrentUser) -> NarrationStatusResponse:
    """Poll narration status for a chapter. 404s the same way the chapter itself would."""

    with tenant_connection(user) as connection:
        published_chapter_text(connection, chapter_id)

    return _narration_response(get_status(chapter_id))


@router.get("/character-voices")
def get_character_voices(user: CurrentUser) -> CharacterVoiceListResponse:
    voices = list_character_voices(str(user.id))
    return CharacterVoiceListResponse(
        voices=[
            CharacterVoiceResponse(character_name=name, content_type=voice.content_type)
            for name, voice in sorted(voices.items())
        ]
    )


@router.put("/character-voices/{character_name}")
async def upload_character_voice(
    character_name: str,
    user: CurrentUser,
    ref_text: Annotated[str, Form()],
    audio: Annotated[UploadFile, File()],
) -> CharacterVoiceResponse:
    """Upload (or replace) the reference clip used for one character's dialogue.

    Re-uploading for the same `character_name` at any time replaces the
    previous clip — there is no separate "update" endpoint, this one always
    upserts, which is also why it's a `PUT` rather than a `POST`.
    """

    audio_bytes = await audio.read()
    try:
        saved = save_character_voice(
            user_id=str(user.id),
            character_name=character_name,
            audio_bytes=audio_bytes,
            content_type=audio.content_type or "",
            ref_text=ref_text,
        )
    except VoiceUploadError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return CharacterVoiceResponse(
        character_name=saved.character_name, content_type=saved.content_type
    )


@router.delete("/character-voices/{character_name}", status_code=status.HTTP_204_NO_CONTENT)
def remove_character_voice(character_name: str, user: CurrentUser) -> None:
    deleted = delete_character_voice(user_id=str(user.id), character_name=character_name)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No voice uploaded for that character")
