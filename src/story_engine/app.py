"""Databricks App entry point for Story Engine."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from starlette.responses import Response

from story_engine.api.events import event_stream
from story_engine.api.routes.archive import router as archive_router
from story_engine.api.routes.branches import router as branches_router
from story_engine.api.routes.cast import branch_cast_router
from story_engine.api.routes.cast import router as cast_router
from story_engine.api.routes.chapters import branch_chapters_router
from story_engine.api.routes.chapters import router as chapters_router
from story_engine.api.routes.endings import router as endings_router
from story_engine.api.routes.events import router as events_router
from story_engine.api.routes.narration import router as narration_router
from story_engine.api.routes.preferences import router as preferences_router
from story_engine.api.routes.progression import me_quota_router
from story_engine.api.routes.progression import router as progression_router
from story_engine.api.routes.revisions import router as revisions_router
from story_engine.api.routes.stories import router as stories_router
from story_engine.api.routes.traces import router as traces_router
from story_engine.api.routes.voice import router as voice_router
from story_engine.api.routes.world import router as world_router
from story_engine.api.settings import load_settings
from story_engine.domain.events import ClientGenerationEvent, PublicAgentLabel
from story_engine.domain.models import ChapterStatus
from story_engine.persistence.lakebase import lakebase_is_ready


class SPAStaticFiles(StaticFiles):
    """Serve the static application shell for browser deep links."""

    async def get_response(self, path: str, scope: object) -> Response:
        response = await super().get_response(path, scope)  # type: ignore[arg-type]
        if response.status_code == 404 and "." not in path:
            return await super().get_response("index.html", scope)  # type: ignore[arg-type]
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="Story Engine", version="0.1.0")

    if load_settings().local_dev_mode:
        # Only reachable when a developer explicitly exports
        # `STORY_ENGINE_LOCAL_DEV=1` (never set by databricks.yml) — lets
        # `npm run dev` on its own port (e.g. localhost:3000) call this API
        # directly instead of 404ing against its own dev server. The
        # deployed App serves the frontend from the same origin (see the
        # SPA static mount below) and never needs or enables this.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(stories_router)
    app.include_router(branches_router)
    app.include_router(chapters_router)
    app.include_router(branch_chapters_router)
    app.include_router(events_router)
    app.include_router(preferences_router)
    app.include_router(progression_router)
    app.include_router(me_quota_router)
    app.include_router(traces_router)
    app.include_router(world_router)
    app.include_router(endings_router)
    app.include_router(revisions_router)
    app.include_router(cast_router)
    app.include_router(branch_cast_router)
    app.include_router(archive_router)
    app.include_router(narration_router)
    app.include_router(voice_router)

    @app.get("/api/v1/health", include_in_schema=False)
    def health() -> JSONResponse:
        settings = load_settings()
        return JSONResponse(
            {
                "status": "ok",
                "environment": settings.environment,
                "lakebase_resource_bound": settings.database_resource_bound,
                "llm_configured": settings.llm_configured,
            }
        )

    @app.get("/api/v1/readiness", include_in_schema=False)
    def readiness() -> JSONResponse:
        settings = load_settings()
        if not lakebase_is_ready(settings):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready"})

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
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="studio")

    return app


app = create_app()
