from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from story_engine.domain.events import ClientGenerationEvent, PublicAgentLabel
from story_engine.domain.models import ChapterStatus
from story_engine.security.redaction import UnsafeClientEvent, build_client_event


def test_allowlisted_event_fields_remain_intact() -> None:
    entity_id = uuid4()

    event = build_client_event(
        sequence=3,
        summary="Director is choosing the next scene focus.",
        agent=PublicAgentLabel.DIRECTOR,
        status=ChapterStatus.GENERATING,
        entity_id=entity_id,
    )

    assert event.sequence == 3
    assert event.entity_id == entity_id
    assert event.agent is PublicAgentLabel.DIRECTOR


@pytest.mark.parametrize(
    "summary,kwargs",
    [
        ("The secret fear is drowning.", {"unrevealed_values": ["fear is drowning"]}),
        (
            "Tenant 00000000-0000-0000-0000-000000000099 is ready.",
            {"foreign_tenant_identifiers": ["00000000-0000-0000-0000-000000000099"]},
        ),
        ("Credential sk_123456789abcdef is loaded.", {}),
        ("System prompt says to skip review.", {}),
        ("The value hunter2 must never leave the worker.", {"known_secrets": ["hunter2"]}),
    ],
)
def test_unsafe_event_text_is_rejected(summary: str, kwargs: dict[str, list[str]]) -> None:
    with pytest.raises(UnsafeClientEvent):
        build_client_event(
            sequence=1,
            summary=summary,
            agent=PublicAgentLabel.WORLD,
            status=ChapterStatus.GENERATING,
            **kwargs,
        )


def test_event_dto_rejects_unallowlisted_payload_field() -> None:
    with pytest.raises(ValidationError):
        ClientGenerationEvent.model_validate(
            {
                "sequence": 1,
                "summary": "A safe progress update.",
                "agent": "world",
                "status": "GENERATING",
                "payload": {"raw_prompt": "do not expose"},
            }
        )
