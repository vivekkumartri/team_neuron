"""Allowlisted SSE serialization for generation activity."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from sse_starlette.sse import ServerSentEvent  # type: ignore[attr-defined]

from story_engine.domain.events import ClientGenerationEvent


async def event_stream(events: Iterable[ClientGenerationEvent]) -> AsyncIterator[ServerSentEvent]:
    """Yield the only public event DTO; raw agent payloads never enter this stream."""

    for event in events:
        yield ServerSentEvent(
            data=event.model_dump_json(), event="generation-progress", id=str(event.sequence)
        )
