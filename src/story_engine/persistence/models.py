"""Persistence-facing models that avoid accepting cross-user snapshots."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PersonalizationSnapshotRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: UUID
    version: int = Field(ge=1)


class StoryCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    title: str = Field(min_length=1, max_length=200)
    personalization_enabled: bool = False
    personalization_snapshot: PersonalizationSnapshotRef | None = None

    @model_validator(mode="after")
    def validate_personalization(self) -> StoryCreate:
        if not self.personalization_enabled and self.personalization_snapshot is not None:
            raise ValueError("Disabled stories cannot select a personalization snapshot")
        if self.personalization_snapshot and self.personalization_snapshot.user_id != self.user_id:
            raise ValueError("A story can only select its owner's personalization snapshot")
        return self
