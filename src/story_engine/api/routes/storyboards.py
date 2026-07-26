"""Tenant-scoped storyboard job and deterministic comic panel reads."""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from starlette.responses import Response

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.api.settings import load_settings
from story_engine.services.databricks_jobs import JobLaunchError, get_job_launcher
from story_engine.storyboard.models import StoryboardSourceLine
from story_engine.storyboard.transcript import RawDialogue, RawScene, build_transcript

router = APIRouter(prefix="/api/v1", tags=["storyboards"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class StoryboardDialogue(BaseModel):
    line_number: int
    speaker_entity_id: UUID | None
    speaker_name: str | None
    line_text: str


class StoryboardCharacter(BaseModel):
    entity_id: UUID
    name: str
    reference_asset_id: UUID | None


class StoryboardSceneResponse(BaseModel):
    scene_number: int
    status: str
    image_url: str | None
    location: str
    action: str
    emotion: str
    characters: list[StoryboardCharacter]
    dialogue: list[StoryboardDialogue]


class StoryboardResponse(BaseModel):
    job_id: UUID
    chapter_id: UUID
    status: str
    error_message: str | None = None
    scenes: list[StoryboardSceneResponse] = Field(default_factory=list)


def _job_response(
    job_id: UUID, chapter_id: UUID, job_status: str, error: object
) -> StoryboardResponse:
    return StoryboardResponse(
        job_id=job_id,
        chapter_id=chapter_id,
        status=job_status,
        error_message=str(error) if error is not None else None,
    )


@router.post(
    "/chapters/{chapter_id}/storyboard",
    response_model=StoryboardResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_storyboard(chapter_id: UUID, user: CurrentUser) -> StoryboardResponse:
    created = False
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.id FROM chapters c JOIN branches b ON b.id = c.branch_id "
                "WHERE c.id = %s AND c.status = 'PUBLISHED'",
                (chapter_id,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
                )

            cursor.execute(
                "SELECT id, status, error_message FROM storyboard_jobs WHERE chapter_id = %s",
                (chapter_id,),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.execute(
                    "INSERT INTO storyboard_jobs (chapter_id, requested_by_user_id, status) "
                    "VALUES (%s, %s, 'QUEUED') RETURNING id",
                    (chapter_id, user.id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Storyboard job could not be created",
                    )
                job_id = UUID(str(cast(tuple[Any, ...], row)[0]))
                job_status = "QUEUED"
                error_message = None
                created = True
            else:
                values = cast(tuple[Any, ...], existing)
                job_id = UUID(str(values[0]))
                job_status = str(values[1])
                error_message = values[2]
                if job_status == "FAILED":
                    cursor.execute(
                        "UPDATE storyboard_jobs SET status = 'QUEUED', error_message = NULL, "
                        "updated_at = now() WHERE id = %s",
                        (job_id,),
                    )
                    job_status = "QUEUED"
                    error_message = None
                    created = True
        connection.commit()

    if created:
        try:
            get_job_launcher(load_settings()).launch(job_key="storyboard_job", job_id=job_id)
        except JobLaunchError as error:
            with tenant_connection(user) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE storyboard_jobs SET status = 'FAILED', "
                        "error_message = 'Storyboard worker could not be started.', "
                        "updated_at = now() "
                        "WHERE id = %s",
                        (job_id,),
                    )
                connection.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storyboard worker could not be started",
            ) from error

    return _job_response(job_id, chapter_id, job_status, error_message)


@router.get("/chapters/{chapter_id}/storyboard", response_model=StoryboardResponse)
def get_storyboard(chapter_id: UUID, user: CurrentUser) -> StoryboardResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, status, error_message FROM storyboard_jobs WHERE chapter_id = %s",
                (chapter_id,),
            )
            job_row = cursor.fetchone()
            if job_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Storyboard not created"
                )
            job_id, job_status, error_message = cast(tuple[Any, ...], job_row)
            job_uuid = UUID(str(job_id))

            cursor.execute(
                "SELECT sc.id, sc.summary FROM scenes sc WHERE sc.chapter_id = %s "
                "ORDER BY sc.scene_index",
                (chapter_id,),
            )
            source_scenes: list[RawScene] = []
            for scene_id, summary in cast(list[tuple[Any, ...]], cursor.fetchall()):
                cursor.execute(
                    "SELECT d.speaker_entity_id, e.name, d.line_text FROM dialogue d "
                    "LEFT JOIN entities e ON e.id = d.speaker_entity_id "
                    "WHERE d.scene_id = %s ORDER BY d.line_index",
                    (scene_id,),
                )
                source_scenes.append(
                    RawScene(
                        str(summary),
                        tuple(
                            RawDialogue(
                                UUID(str(row[0])) if row[0] is not None else None,
                                str(row[1]) if row[1] is not None else None,
                                str(row[2]),
                            )
                            for row in cast(list[tuple[Any, ...]], cursor.fetchall())
                        ),
                    )
                )
            source_lines = build_transcript(source_scenes)

            cursor.execute(
                "SELECT id, name, "
                "(SELECT r.asset_id FROM character_visual_references r "
                "WHERE r.entity_id = e.id AND r.story_id = e.story_id AND r.is_current) "
                "FROM entities e WHERE e.story_id = (SELECT b.story_id FROM chapters c "
                "JOIN branches b ON b.id = c.branch_id WHERE c.id = %s) "
                "AND e.entity_type = 'character' ORDER BY e.created_at",
                (chapter_id,),
            )
            characters = {
                UUID(str(row[0])): StoryboardCharacter(
                    entity_id=UUID(str(row[0])),
                    name=str(row[1]),
                    reference_asset_id=UUID(str(row[2])) if row[2] is not None else None,
                )
                for row in cast(list[tuple[Any, ...]], cursor.fetchall())
            }

            cursor.execute(
                "SELECT scene_index, source_line_start, source_line_end, "
                "character_entity_ids, panel_asset_id, status, location, action, emotion "
                "FROM storyboard_scenes WHERE job_id = %s ORDER BY scene_index",
                (job_uuid,),
            )
            scenes: list[StoryboardSceneResponse] = []
            for row in cast(list[tuple[Any, ...]], cursor.fetchall()):
                (
                    scene_index,
                    line_start,
                    line_end,
                    entity_ids,
                    panel_asset_id,
                    scene_status,
                    location,
                    action,
                    emotion,
                ) = row
                source_slice: list[StoryboardSourceLine] = list(
                    source_lines[int(line_start) - 1 : int(line_end)]
                )
                scene_characters = [
                    characters[UUID(str(entity_id))]
                    for entity_id in cast(list[object], entity_ids)
                    if UUID(str(entity_id)) in characters
                ]
                scenes.append(
                    StoryboardSceneResponse(
                        scene_number=int(scene_index),
                        status=str(scene_status),
                        image_url=(
                            f"/api/v1/storyboard-assets/{panel_asset_id}"
                            if panel_asset_id is not None
                            else None
                        ),
                        location=str(location),
                        action=str(action),
                        emotion=str(emotion),
                        characters=scene_characters,
                        dialogue=[
                            StoryboardDialogue(
                                line_number=line.line_number,
                                speaker_entity_id=line.speaker_entity_id,
                                speaker_name=line.speaker_name,
                                line_text=line.text,
                            )
                            for line in source_slice
                        ],
                    )
                )

    return StoryboardResponse(
        job_id=job_uuid,
        chapter_id=chapter_id,
        status=str(job_status),
        error_message=str(error_message) if error_message is not None else None,
        scenes=scenes,
    )


@router.get("/storyboard-assets/{asset_id}")
def get_storyboard_asset(asset_id: UUID, user: CurrentUser) -> Response:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT mime_type, content FROM storyboard_assets WHERE id = %s",
                (asset_id,),
            )
            row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storyboard asset not found"
        )
    mime_type, content = cast(tuple[Any, ...], row)
    return Response(content=bytes(content), media_type=str(mime_type))
