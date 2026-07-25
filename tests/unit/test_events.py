from __future__ import annotations

import asyncio

from story_engine.api.events import event_stream
from story_engine.domain.events import ClientGenerationEvent, PublicAgentLabel
from story_engine.domain.models import ChapterStatus


def test_sse_stream_serializes_only_public_event_dto() -> None:
    event = ClientGenerationEvent(
        sequence=1,
        summary="Director is selecting a focal character.",
        agent=PublicAgentLabel.DIRECTOR,
        status=ChapterStatus.GENERATING,
    )

    async def collect() -> list[object]:
        return [item async for item in event_stream((event,))]

    streamed = asyncio.run(collect())
    assert len(streamed) == 1
    assert "focal character" in streamed[0].data
