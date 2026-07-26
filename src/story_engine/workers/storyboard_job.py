"""Async worker for chapter storyboard planning and image generation."""

from __future__ import annotations

import argparse
import hashlib
import logging
from typing import Any, cast
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from story_engine.agents.provider import OpenAIResponsesProvider
from story_engine.api.settings import load_settings
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.persistence.tenant_context import set_tenant_context
from story_engine.storyboard.image_provider import OpenAIImageProvider
from story_engine.storyboard.models import CharacterVisualProfile, StoryboardPlan, StoryboardScene
from story_engine.storyboard.prompts import canonical_reference_prompt, scene_image_prompt
from story_engine.storyboard.segmentation import parse_storyboard_plan, storyboard_planner_prompt
from story_engine.storyboard.service import name_lookup, planner_input
from story_engine.storyboard.transcript import RawDialogue, RawScene, build_transcript
from story_engine.workers.generation_job import _load_openai_api_key

logger = logging.getLogger(__name__)


def _insert_asset(
    connection: Connection[object], *, story_id: UUID, kind: str, content: bytes, mime_type: str
) -> UUID:
    digest = hashlib.sha256(content).hexdigest()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO storyboard_assets (story_id, asset_kind, mime_type, content, sha256) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (story_id, kind, mime_type, content, digest),
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Storyboard asset was not stored")
    return UUID(str(cast(tuple[Any, ...], row)[0]))


def _claim_job(connection: Connection[object], job_id: UUID) -> tuple[UUID, UUID] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE storyboard_jobs SET status = 'RUNNING', updated_at = now() "
            "WHERE id = %s AND status = 'QUEUED' RETURNING chapter_id, requested_by_user_id",
            (job_id,),
        )
        row = cursor.fetchone()
    connection.commit()
    if row is None:
        return None
    values = cast(tuple[Any, ...], row)
    return UUID(str(values[0])), UUID(str(values[1]))


def _load_context(
    connection: Connection[object], chapter_id: UUID
) -> tuple[
    UUID,
    UUID,
    str,
    tuple[RawScene, ...],
    list[CharacterVisualProfile],
    dict[UUID, tuple[str, bytes]],
]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.branch_id, b.story_id, COALESCE(s.scenario, s.title) "
            "FROM chapters c JOIN branches b ON b.id = c.branch_id "
            "JOIN stories s ON s.id = b.story_id WHERE c.id = %s AND c.status = 'PUBLISHED'",
            (chapter_id,),
        )
        chapter_row = cursor.fetchone()
        if chapter_row is None:
            raise RuntimeError("Published chapter was not found")
        branch_id, story_id, scenario = cast(tuple[Any, ...], chapter_row)

        cursor.execute(
            "SELECT sc.id, sc.summary FROM scenes sc WHERE sc.chapter_id = %s "
            "ORDER BY sc.scene_index",
            (chapter_id,),
        )
        raw_scenes: list[RawScene] = []
        for scene_id, summary in cast(list[tuple[Any, ...]], cursor.fetchall()):
            cursor.execute(
                "SELECT d.speaker_entity_id, e.name, d.line_text FROM dialogue d "
                "LEFT JOIN entities e ON e.id = d.speaker_entity_id "
                "WHERE d.scene_id = %s ORDER BY d.line_index",
                (scene_id,),
            )
            dialogue = tuple(
                RawDialogue(
                    UUID(str(row[0])) if row[0] is not None else None,
                    str(row[1]) if row[1] is not None else None,
                    str(row[2]),
                )
                for row in cast(list[tuple[Any, ...]], cursor.fetchall())
            )
            raw_scenes.append(RawScene(str(summary), dialogue))

        cursor.execute(
            "SELECT e.id, e.name, e.background_story, e.visual_description, "
            "r.asset_id, a.mime_type, a.content "
            "FROM entities e "
            "LEFT JOIN character_visual_references r ON r.entity_id = e.id "
            "AND r.story_id = e.story_id AND r.is_current "
            "LEFT JOIN storyboard_assets a ON a.id = r.asset_id "
            "WHERE e.story_id = %s AND e.entity_type = 'character' ORDER BY e.created_at",
            (story_id,),
        )
        profiles: list[CharacterVisualProfile] = []
        reference_images: dict[UUID, tuple[str, bytes]] = {}
        for row in cast(list[tuple[Any, ...]], cursor.fetchall()):
            entity_id = UUID(str(row[0]))
            asset_id = UUID(str(row[4])) if row[4] is not None else None
            profiles.append(
                CharacterVisualProfile(
                    entity_id=entity_id,
                    name=str(row[1]),
                    background_story=str(row[2] or ""),
                    visual_description=str(row[3] or ""),
                    reference_asset_id=asset_id,
                )
            )
            if asset_id is not None and row[5] is not None and row[6] is not None:
                reference_images[entity_id] = (str(row[5]), bytes(row[6]))
    return (
        UUID(str(branch_id)),
        UUID(str(story_id)),
        str(scenario),
        tuple(raw_scenes),
        profiles,
        reference_images,
    )


def _ensure_character_references(
    connection: Connection[object],
    *,
    story_id: UUID,
    chapter_id: UUID,
    requester_id: UUID,
    profiles: list[CharacterVisualProfile],
    reference_images: dict[UUID, tuple[str, bytes]],
    image_provider: OpenAIImageProvider,
    image_model: str,
    image_quality: str,
) -> list[CharacterVisualProfile]:
    result: list[CharacterVisualProfile] = []
    for profile in profiles:
        if profile.reference_asset_id is not None:
            result.append(profile)
            continue
        image = image_provider.generate(
            prompt=canonical_reference_prompt(profile),
            model=image_model,
            reference_images=(),
            quality=image_quality,
        )
        asset_id = _insert_asset(
            connection,
            story_id=story_id,
            kind="CHARACTER_REFERENCE",
            content=image,
            mime_type="image/png",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO character_visual_references "
                "(story_id, entity_id, asset_id, source, reference_prompt, "
                "source_chapter_id, version) "
                "VALUES (%s, %s, %s, 'GENERATED', %s, %s, 1)",
                (
                    story_id,
                    profile.entity_id,
                    asset_id,
                    canonical_reference_prompt(profile),
                    chapter_id,
                ),
            )
        reference_images[profile.entity_id] = ("image/png", image)
        result.append(profile.model_copy(update={"reference_asset_id": asset_id}))
        connection.commit()
        set_tenant_context(connection, requester_id)
    return result


def _load_saved_plan(
    connection: Connection[object], job_id: UUID
) -> tuple[StoryboardPlan | None, set[int]]:
    """Recover a partial plan so retries do not repeat successful panel work."""

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT scene_index, source_line_start, source_line_end, character_entity_ids, "
            "location, action, emotion, image_prompt, status "
            "FROM storyboard_scenes WHERE job_id = %s ORDER BY scene_index",
            (job_id,),
        )
        rows = cast(list[tuple[Any, ...]], cursor.fetchall())
    if not rows:
        return None, set()
    scenes: list[StoryboardScene] = []
    completed: set[int] = set()
    for row in rows:
        (
            scene_index,
            start,
            end,
            entity_ids,
            location,
            action,
            emotion,
            image_prompt,
            scene_status,
        ) = row
        scenes.append(
            StoryboardScene(
                scene_number=int(scene_index),
                dialogue_start=int(start),
                dialogue_end=int(end),
                character_entity_ids=tuple(
                    UUID(str(value)) for value in cast(list[object], entity_ids)
                ),
                location=str(location),
                action=str(action),
                emotion=str(emotion),
                image_prompt=str(image_prompt),
            )
        )
        if str(scene_status) == "SUCCEEDED":
            completed.add(int(scene_index))
    return StoryboardPlan(scenes=tuple(scenes)), completed


def run_storyboard_job(job_id: UUID) -> None:
    settings = load_settings()
    api_key = _load_openai_api_key(settings)

    with lakebase_connection(settings) as connection:
        claimed = _claim_job(connection, job_id)
        if claimed is None:
            logger.info("Storyboard job %s is not claimable", job_id)
            return
        chapter_id, requester_id = claimed
        set_tenant_context(connection, requester_id)
        try:
            _, story_id, scenario, raw_scenes, profiles, reference_images = _load_context(
                connection, chapter_id
            )
            source_lines = build_transcript(raw_scenes)
            saved_plan, completed_scenes = _load_saved_plan(connection, job_id)
            if saved_plan is None:
                provider = OpenAIResponsesProvider(api_key=api_key)
                plan_raw = provider.complete(
                    system_prompt=storyboard_planner_prompt(),
                    user_data=planner_input(
                        scenario=scenario, profiles=profiles, source_lines=source_lines
                    ),
                    model=settings.openai_model,
                )
                plan = parse_storyboard_plan(
                    plan_raw,
                    source_lines=source_lines,
                    characters_by_name=name_lookup(profiles),
                )
            else:
                plan = saved_plan
            image_provider = OpenAIImageProvider(api_key=api_key)
            profiles = _ensure_character_references(
                connection,
                story_id=story_id,
                chapter_id=chapter_id,
                requester_id=requester_id,
                profiles=profiles,
                reference_images=reference_images,
                image_provider=image_provider,
                image_model=settings.storyboard_image_model,
                image_quality=settings.storyboard_image_quality,
            )
            profiles_by_id = {profile.entity_id: profile for profile in profiles}

            if saved_plan is None:
                with connection.cursor() as cursor:
                    for scene in plan.scenes:
                        cursor.execute(
                            "INSERT INTO storyboard_scenes "
                            "(job_id, scene_index, source_line_start, source_line_end, "
                            "character_entity_ids, location, action, emotion, "
                            "image_prompt, status) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PLANNED')",
                            (
                                job_id,
                                scene.scene_number,
                                scene.dialogue_start,
                                scene.dialogue_end,
                                Jsonb([str(entity_id) for entity_id in scene.character_entity_ids]),
                                scene.location,
                                scene.action,
                                scene.emotion,
                                scene.image_prompt,
                            ),
                        )
                connection.commit()
                set_tenant_context(connection, requester_id)

            for scene in plan.scenes:
                if scene.scene_number in completed_scenes:
                    continue
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE storyboard_scenes SET status = 'GENERATING' "
                        "WHERE job_id = %s AND scene_index = %s",
                        (job_id, scene.scene_number),
                    )
                connection.commit()
                set_tenant_context(connection, requester_id)
                scene_profiles = [
                    profiles_by_id[entity_id] for entity_id in scene.character_entity_ids
                ]
                refs = [reference_images[entity_id] for entity_id in scene.character_entity_ids]
                panel = image_provider.generate(
                    prompt=scene_image_prompt(scene, scene_profiles),
                    model=settings.storyboard_image_model,
                    reference_images=refs,
                    quality=settings.storyboard_image_quality,
                )
                panel_asset_id = _insert_asset(
                    connection,
                    story_id=story_id,
                    kind="STORYBOARD_PANEL",
                    content=panel,
                    mime_type="image/png",
                )
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE storyboard_scenes SET panel_asset_id = %s, status = 'SUCCEEDED' "
                        "WHERE job_id = %s AND scene_index = %s",
                        (panel_asset_id, job_id, scene.scene_number),
                    )
                connection.commit()
                set_tenant_context(connection, requester_id)

            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE storyboard_jobs SET status = 'SUCCEEDED', updated_at = now() "
                    "WHERE id = %s",
                    (job_id,),
                )
            connection.commit()
        except Exception:
            logger.exception("Storyboard job %s failed", job_id)
            connection.rollback()
            set_tenant_context(connection, requester_id)
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE storyboard_jobs SET status = 'FAILED', "
                    "error_message = 'Storyboard generation failed. Retry the request.', "
                    "updated_at = now() WHERE id = %s",
                    (job_id,),
                )
            connection.commit()
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True, type=UUID)
    run_storyboard_job(parser.parse_args().job_id)


if __name__ == "__main__":
    main()
