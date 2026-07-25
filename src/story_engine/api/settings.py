"""Runtime settings sourced only from the environment or Databricks resources."""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: str = Field(default="development", min_length=1, max_length=32)
    database_host: str | None = None
    database_name: str | None = None
    database_user: str | None = None

    @property
    def database_resource_bound(self) -> bool:
        return all((self.database_host, self.database_name, self.database_user))


def load_settings() -> RuntimeSettings:
    """Read injected Lakebase connection metadata without accepting a raw URL."""

    return RuntimeSettings(
        environment=os.getenv("STORY_ENGINE_ENV", "development"),
        database_host=os.getenv("PGHOST"),
        database_name=os.getenv("PGDATABASE"),
        database_user=os.getenv("PGUSER"),
    )
