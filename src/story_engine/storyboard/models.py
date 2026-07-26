"""Provider-independent storyboard contracts.

The scene plan points at source dialogue ranges. It never carries a rewritten
copy of the dialogue, which keeps rendering deterministic and auditable.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CharacterVisualProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: UUID
    name: str = Field(min_length=1, max_length=80)
    background_story: str = Field(default="", max_length=2_000)
    visual_description: str = Field(default="", max_length=1_000)
    reference_asset_id: UUID | None = None


class StoryboardSourceLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_number: int = Field(ge=1)
    speaker_entity_id: UUID | None = None
    speaker_name: str | None = Field(default=None, max_length=80)
    text: str = Field(min_length=1, max_length=4_000)


class StoryboardScene(BaseModel):
    model_config = ConfigDict(frozen=True)

    scene_number: int = Field(ge=1)
    dialogue_start: int = Field(ge=1)
    dialogue_end: int = Field(ge=1)
    character_entity_ids: tuple[UUID, ...] = Field(min_length=1, max_length=12)
    location: str = Field(min_length=1, max_length=300)
    action: str = Field(min_length=1, max_length=600)
    emotion: str = Field(min_length=1, max_length=200)
    image_prompt: str = Field(min_length=1, max_length=2_000)


class StoryboardPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenes: tuple[StoryboardScene, ...] = Field(min_length=1, max_length=12)


class StoryboardJobStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: UUID
    chapter_id: UUID
    status: str
    error_message: str | None = None
