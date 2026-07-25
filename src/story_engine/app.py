"""Databricks App entry point for Story Engine."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from story_engine.api.events import event_stream
from story_engine.api.settings import load_settings
from story_engine.domain.events import ClientGenerationEvent, PublicAgentLabel
from story_engine.domain.models import ChapterStatus


def create_app() -> FastAPI:
    app = FastAPI(title="Story Engine", version="0.1.0")

    @app.get("/api/v1/health", include_in_schema=False)
    def health() -> JSONResponse:
        settings = load_settings()
        return JSONResponse(
            {
                "status": "ok",
                "environment": settings.environment,
                "lakebase_resource_bound": settings.database_resource_bound,
            }
        )

    @app.get("/api/v1/generation-events/demo", include_in_schema=False)
    async def demo_generation_events() -> EventSourceResponse:
        """Temporary demonstrator; production reads redacted events from Lakebase."""

        events = (
            ClientGenerationEvent(
                sequence=1,
                summary="Director is selecting the focal character.",
                agent=PublicAgentLabel.DIRECTOR,
                status=ChapterStatus.GENERATING,
            ),
            ClientGenerationEvent(
                sequence=2,
                summary="World is checking branch continuity.",
                agent=PublicAgentLabel.WORLD,
                status=ChapterStatus.EVALUATING,
            ),
        )
        return EventSourceResponse(event_stream(events))

    static_dir = Path(__file__).resolve().parents[2] / "web" / "out"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="studio")

    return app


app = create_app()
