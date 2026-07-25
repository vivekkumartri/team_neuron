"""Durable job submission contracts."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GenerationJobSubmit(BaseModel):
    model_config = ConfigDict(frozen=True)

    branch_id: UUID
    requested_by_user_id: UUID
    idempotency_key: str = Field(min_length=16, max_length=128)
