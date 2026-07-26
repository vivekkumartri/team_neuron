"""Runtime settings sourced only from the environment or Databricks resources."""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field

try:
    # Local-dev-only convenience: load a gitignored `.env` file (repo root)
    # into the process environment once, at import time, so a developer
    # doesn't have to re-`export` OPENAI_API_KEY/LOCAL_DATABASE_URL/etc. in
    # every new terminal. `python-dotenv` is a `[dev]`-only dependency (see
    # pyproject.toml) and is never installed in the deployed App's runtime,
    # so this import always fails there and this becomes a no-op — real
    # Databricks-injected env vars are the only source in production either
    # way. `load_dotenv()` never overrides a variable that's already set in
    # the environment, so an explicit `export` still always wins locally too.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: str = Field(default="development", min_length=1, max_length=32)
    database_host: str | None = None
    database_name: str | None = None
    database_user: str | None = None
    database_endpoint: str | None = None
    # Local-only escape hatch (docker-compose Postgres, no Databricks/Lakebase
    # OAuth available). Never set in the deployed App — `databricks.yml` only
    # ever injects PGHOST/PGDATABASE/PGUSER/ENDPOINT_NAME, never this var —
    # so this path is structurally unreachable in production regardless of
    # what a request or environment claims.
    local_database_url: str | None = None
    # Same idea, but for identity: the deployed App always gets real
    # `x-forwarded-user`/`x-forwarded-email` headers from the Databricks Apps
    # reverse proxy (see `api/auth.py`). Locally there is no such proxy, so
    # this lets a developer opt in to a single fixed dev identity instead of
    # every request 401ing. Off by default; must be deliberately exported.
    local_dev_mode: bool = False
    openai_api_key: str | None = None
    openai_model: str = Field(default="gpt-5.6-sol", min_length=1, max_length=100)
    storyboard_image_model: str = Field(default="gpt-image-2", min_length=1, max_length=100)
    storyboard_image_quality: str = Field(default="low", pattern="^(low|medium|high)$")
    openai_secret_scope: str = Field(default="story-engine-openai", min_length=1)
    openai_secret_key: str = Field(default="openai-api-key", min_length=1)
    openai_transcription_model: str = Field(default="whisper-1", min_length=1, max_length=100)
    openai_tts_model: str = Field(default="tts-1", min_length=1, max_length=100)
    narrator_voice: str = Field(default="alloy", min_length=1, max_length=64)
    indicf5_base_url: str | None = None
    # IndicF5 zero-shot synthesis on a non-CUDA device (MPS/CPU) has been
    # observed running well below real-time (e.g. ~15x slower than the
    # clip's own duration on Apple Silicon MPS) — a single longer dialogue
    # line can legitimately take a couple of minutes. This is only ever hit
    # from `services/narration_jobs.py`'s background thread, never inline in
    # an HTTP request, so a generous timeout costs nothing but wall-clock
    # time on that thread.
    indicf5_timeout_seconds: float = Field(default=1200.0, gt=0)

    @property
    def database_resource_bound(self) -> bool:
        if self.local_database_url:
            return True
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

    @property
    def indicf5_configured(self) -> bool:
        return bool(self.indicf5_base_url)


def load_settings() -> RuntimeSettings:
    """Read injected Lakebase connection metadata without accepting a raw URL."""

    return RuntimeSettings(
        environment=os.getenv("STORY_ENGINE_ENV", "development"),
        database_host=os.getenv("PGHOST"),
        database_name=os.getenv("PGDATABASE"),
        database_user=os.getenv("PGUSER"),
        database_endpoint=os.getenv("ENDPOINT_NAME"),
        local_database_url=os.getenv("LOCAL_DATABASE_URL"),
        local_dev_mode=os.getenv("STORY_ENGINE_LOCAL_DEV", "").strip().lower()
        in ("1", "true", "yes"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"),
        storyboard_image_model=os.getenv("STORYBOARD_IMAGE_MODEL", "gpt-image-2"),
        storyboard_image_quality=os.getenv("STORYBOARD_IMAGE_QUALITY", "low"),
        openai_secret_scope=os.getenv("OPENAI_SECRET_SCOPE", "story-engine-openai"),
        openai_secret_key=os.getenv("OPENAI_SECRET_KEY", "openai-api-key"),
        openai_transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", "tts-1"),
        narrator_voice=os.getenv("NARRATOR_VOICE", "alloy"),
        indicf5_base_url=os.getenv("INDICF5_BASE_URL"),
        indicf5_timeout_seconds=float(os.getenv("INDICF5_TIMEOUT_SECONDS", "1200")),
    )
