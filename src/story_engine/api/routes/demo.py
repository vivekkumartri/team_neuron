"""Demo mode: serves canned, pre-generated stories straight off local disk.

No database, no RLS, no LLM calls — this is deliberately the simplest
possible read path in the whole app, because its entire purpose is to keep
working when the normal one can't (no network, a burned-through OpenAI
quota, a laptop demo with no Postgres running). See
`services/demo_store.py` for the on-disk bundle format and
`scripts/export_demo_story.py` for how a bundle gets created.

Unauthenticated on purpose: the content is static and non-tenant, and
demo mode needs to work even before a user is provisioned.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from story_engine.services.demo_store import (
    DemoStoryNotFoundError,
    UnsafeDemoPathError,
    list_demo_stories,
    load_demo_story,
    resolve_asset_path,
)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoStorySummaryResponse(BaseModel):
    id: str
    title: str
    tagline: str
    seed_prompt: str
    cover_asset_url: str | None = None


class DemoDialogueLine(BaseModel):
    speaker_name: str | None = None
    line_text: str


class DemoStoryboardScene(BaseModel):
    scene_number: int
    location: str = ""
    action: str = ""
    emotion: str = ""
    image_asset_url: str | None = None
    dialogue: list[DemoDialogueLine] = []


class DemoChapter(BaseModel):
    chapter_index: int
    title: str
    text: str
    narration_asset_url: str | None = None
    storyboard: list[DemoStoryboardScene] = []


class DemoCastMember(BaseModel):
    name: str
    role: str = ""
    traits: str = ""


class DemoStoryDetail(BaseModel):
    id: str
    title: str
    tagline: str
    seed_prompt: str
    language: str = "en"
    cover_asset_url: str | None = None
    cast: list[DemoCastMember] = []
    chapters: list[DemoChapter] = []


@router.get("/stories", response_model=list[DemoStorySummaryResponse])
def get_demo_stories() -> list[DemoStorySummaryResponse]:
    return [DemoStorySummaryResponse.model_validate(summary) for summary in list_demo_stories()]


@router.get("/stories/{demo_id}", response_model=DemoStoryDetail)
def get_demo_story(demo_id: str) -> DemoStoryDetail:
    try:
        story = load_demo_story(demo_id)
    except (DemoStoryNotFoundError, UnsafeDemoPathError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demo story not found"
        ) from error
    return DemoStoryDetail.model_validate(story)


@router.get("/assets/{demo_id}/{asset_path:path}")
def get_demo_asset(demo_id: str, asset_path: str) -> FileResponse:
    """`asset_path` is `cover.png` (story-level) or `ch1/scene_1.png` (chapter-level)."""

    try:
        path = resolve_asset_path(demo_id, asset_path)
    except UnsafeDemoPathError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from error
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return FileResponse(path)
