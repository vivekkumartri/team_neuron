"""Published-chapter read endpoint.

Only ever reads `chapters`/`scenes`/`dialogue`/`choices` — the published,
canon tables — never `candidate_chapters` staging rows (design.md "Loophole
and Integrity Guards": a rejected candidate must never be reachable through a
published-chapter query).
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection

router = APIRouter(prefix="/api/v1/chapters", tags=["chapters"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class DialogueLine(BaseModel):
    line_index: int
    speaker_entity_id: UUID | None
    line_text: str


class Scene(BaseModel):
    scene_index: int
    summary: str
    dialogue: list[DialogueLine]


class Choice(BaseModel):
    choice_index: int
    label: str
    progression_mode: str


class ChapterResponse(BaseModel):
    id: UUID
    branch_id: UUID
    chapter_index: int
    status: str
    published_at: str | None
    scenes: list[Scene]
    choices: list[Choice]


@router.get("/{chapter_id}", response_model=ChapterResponse)
def get_chapter(chapter_id: UUID, user: CurrentUser) -> ChapterResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, branch_id, chapter_index, status, published_at "
                "FROM chapters WHERE id = %s",
                (chapter_id,),
            )
            fetched_chapter_row = cursor.fetchone()
            if fetched_chapter_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
                )
            chapter_row = cast(tuple[Any, ...], fetched_chapter_row)

            cursor.execute(
                "SELECT id, scene_index, summary FROM scenes "
                "WHERE chapter_id = %s ORDER BY scene_index",
                (chapter_id,),
            )
            scene_rows = cast(list[tuple[Any, ...]], cursor.fetchall())

            scenes: list[Scene] = []
            for scene_id, scene_index, summary in scene_rows:
                cursor.execute(
                    "SELECT line_index, speaker_entity_id, line_text FROM dialogue "
                    "WHERE scene_id = %s ORDER BY line_index",
                    (scene_id,),
                )
                dialogue_rows = cast(list[tuple[Any, ...]], cursor.fetchall())
                scenes.append(
                    Scene(
                        scene_index=int(scene_index),
                        summary=str(summary),
                        dialogue=[
                            DialogueLine(
                                line_index=int(li),
                                speaker_entity_id=UUID(str(sid)) if sid is not None else None,
                                line_text=str(text),
                            )
                            for li, sid, text in dialogue_rows
                        ],
                    )
                )

            cursor.execute(
                "SELECT choice_index, label, progression_mode FROM choices "
                "WHERE chapter_id = %s ORDER BY choice_index",
                (chapter_id,),
            )
            choice_rows = cast(list[tuple[Any, ...]], cursor.fetchall())

    return ChapterResponse(
        id=UUID(str(chapter_row[0])),
        branch_id=UUID(str(chapter_row[1])),
        chapter_index=int(chapter_row[2]),
        status=str(chapter_row[3]),
        published_at=str(chapter_row[4]) if chapter_row[4] is not None else None,
        scenes=scenes,
        choices=[
            Choice(choice_index=int(ci), label=str(label), progression_mode=str(mode))
            for ci, label, mode in choice_rows
        ],
    )
