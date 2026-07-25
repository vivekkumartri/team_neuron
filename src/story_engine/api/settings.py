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
    database_endpoint: str | None = None
    openai_api_key: str | None = None
    openai_model: str = Field(default="gpt-5.6-sol", min_length=1, max_length=100)
    openai_secret_scope: str = Field(default="story-engine-openai", min_length=1)
    openai_secret_key: str = Field(default="openai-api-key", min_length=1)
    openai_transcription_model: str = Field(default="whisper-1", min_length=1, max_length=100)
    openai_tts_model: str = Field(default="tts-1", min_length=1, max_length=100)
    narrator_voice: str = Field(default="alloy", min_length=1, max_length=64)

    @property
    def database_resource_bound(self) -> bool:
        return all(
            (
                self.database_host,
                self.database_name,
                self.database_user,
                self.database_endpoint,
            )
        )

    @property
    def llm_configured(self) -> bool:
        """Whether this runtime can make real model calls.

        The key is injected by Databricks and is intentionally never exposed
        from a route, log line, event, or client bundle.
        """

        return bool(self.openai_api_key)


def load_settings() -> RuntimeSettings:
    """Read injected Lakebase connection metadata without accepting a raw URL."""

    return RuntimeSettings(
        environment=os.getenv("STORY_ENGINE_ENV", "development"),
        database_host=os.getenv("PGHOST"),
        database_name=os.getenv("PGDATABASE"),
        database_user=os.getenv("PGUSER"),
        database_endpoint=os.getenv("ENDPOINT_NAME"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"),
        openai_secret_scope=os.getenv("OPENAI_SECRET_SCOPE", "story-engine-openai"),
        openai_secret_key=os.getenv("OPENAI_SECRET_KEY", "openai-api-key"),
        openai_transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", "tts-1"),
        narrator_voice=os.getenv("NARRATOR_VOICE", "alloy"),
    )
