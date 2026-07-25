"""Databricks App entry point for Story Engine."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from story_engine.api.settings import load_settings


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

    return app


app = create_app()
