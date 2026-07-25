"""Builds narrator-voice screenplay text for a published chapter.

This only ever reads from the published `chapters`/`scenes`/`dialogue` tables
(never `candidate_chapters`), the same rule `api/routes/chapters.py`
documents — a rejected/unpublished candidate must never be reachable through
narration either.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from psycopg import Connection


def published_chapter_text(connection: Connection[object], chapter_id: UUID) -> str:
    """Return a plain-text narration script for one published chapter.

    Raises `HTTPException(404)` if the chapter does not exist or is not
    published, matching `chapters.get_chapter`'s not-found behavior.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status FROM chapters WHERE id = %s",
            (chapter_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
        chapter_status = cast(tuple[Any, ...], row)[0]
        if str(chapter_status) != "PUBLISHED":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        cursor.execute(
            "SELECT id, scene_index, summary FROM scenes "
            "WHERE chapter_id = %s ORDER BY scene_index",
            (chapter_id,),
        )
        scene_rows = cast(list[tuple[Any, ...]], cursor.fetchall())

        lines: list[str] = []
        for scene_id, scene_index, summary in scene_rows:
            lines.append(f"Scene {int(scene_index) + 1}. {summary}")
            cursor.execute(
                "SELECT line_index, line_text FROM dialogue "
                "WHERE scene_id = %s ORDER BY line_index",
                (scene_id,),
            )
            dialogue_rows = cast(list[tuple[Any, ...]], cursor.fetchall())
            for _line_index, line_text in dialogue_rows:
                lines.append(str(line_text))

    text = "\n".join(lines).strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter has no narratable content"
        )
    return text
