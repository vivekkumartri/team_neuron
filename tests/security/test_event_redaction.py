"""Task 5J.1: hidden-secret / raw-payload stream leak tests.

Runs in the plain unit suite (no live DB needed) — these assert the redaction
guarantees built into the domain models and SSE row parser themselves.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from story_engine.api.sse import _row_to_event
from story_engine.domain.events import ClientGenerationEvent, PublicAgentLabel
from story_engine.domain.models import ChapterStatus


def test_client_generation_event_rejects_a_smuggled_payload_field() -> None:
    with pytest.raises(ValidationError):
        ClientGenerationEvent(
            sequence=1,
            summary="ok",
            agent=PublicAgentLabel.DIRECTOR,
            status=ChapterStatus.GENERATING,
            payload={"secret": "leak"},  # type: ignore[call-arg]
        )


def test_client_generation_event_rejects_a_smuggled_prompt_field() -> None:
    with pytest.raises(ValidationError):
        ClientGenerationEvent(
            sequence=1,
            summary="ok",
            agent=PublicAgentLabel.DIRECTOR,
            status=ChapterStatus.GENERATING,
            prompt="system prompt text",  # type: ignore[call-arg]
        )


def test_row_to_event_skips_a_malformed_row_instead_of_raising_or_leaking_it() -> None:
    malformed_row = (1, "not-a-real-agent-label", "GENERATING", "summary", None)
    assert _row_to_event(malformed_row) is None


def test_row_to_event_never_produces_a_payload_or_prompt_attribute() -> None:
    row = (1, "director", "GENERATING", "Picking a scene.", None)
    event = _row_to_event(row)
    assert event is not None
    dumped = event.model_dump()
    assert "payload" not in dumped
    assert "prompt" not in dumped
    assert "raw_response" not in dumped
