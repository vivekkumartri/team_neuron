"""Public, intentionally small DTOs for generation progress events."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from story_engine.domain.models import ChapterStatus


class PublicAgentLabel(StrEnum):
    WORLD = "world"
    DIRECTOR = "director"
    STORYTELLER = "storyteller"
    EVALUATOR = "evaluator"
    BUSINESS = "business"


class ClientGenerationEvent(BaseModel):
    """The complete event contract permitted to leave the server boundary.

    It deliberately has no payload, prompt, tool-call, tenant, or reasoning field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=500)
    agent: PublicAgentLabel
    status: ChapterStatus
    entity_id: UUID | None = None

