"""Narrator-voice text-to-speech playback for a published chapter.

Authorization and table access mirror `routes/chapters.py` exactly: the same
`tenant_connection` (RLS-scoped) dependency, and the same published-only read
via `services/narration.published_chapter_text`. TTS itself does not
generate new prose — it only reads back text that is already published, so
none of the content-policy prose gates in `generation_pipeline.py` apply
here (there is nothing new to gate).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import Response

from story_engine.agents.provider import ModelProviderError
from story_engine.agents.voice_provider import OpenAIVoiceProvider
from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.api.settings import load_settings
from story_engine.services.narration import published_chapter_text

router = APIRouter(prefix="/api/v1/chapters", tags=["narration"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]

# OpenAI TTS caps input length per request; keep a safety margin below it.
_MAX_NARRATION_CHARS = 4_000


@router.get("/{chapter_id}/narration")
def get_chapter_narration(chapter_id: UUID, user: CurrentUser) -> Response:
    settings = load_settings()
    if not settings.llm_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Narration is not configured in this environment",
        )

    with tenant_connection(user) as connection:
        text = published_chapter_text(connection, chapter_id)

    provider = OpenAIVoiceProvider(api_key=settings.openai_api_key or "")
    try:
        audio_bytes = provider.synthesize_speech(
            text=text[:_MAX_NARRATION_CHARS],
            model=settings.openai_tts_model,
            voice=settings.narrator_voice,
        )
    except ModelProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Narration synthesis failed"
        ) from error

    return Response(content=audio_bytes, media_type="audio/mpeg")
