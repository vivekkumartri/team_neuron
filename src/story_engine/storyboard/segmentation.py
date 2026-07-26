"""Strict parsing and validation for the one storyboard-planning LLM call."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from story_engine.storyboard.models import StoryboardPlan, StoryboardScene, StoryboardSourceLine


class StoryboardValidationError(ValueError):
    """The model returned a plan that cannot safely reference source dialogue."""


class _SceneDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_number: int = Field(ge=1)
    dialogue_start: int = Field(ge=1)
    dialogue_end: int = Field(ge=1)
    characters: list[str] = Field(min_length=1, max_length=12)
    location: str = Field(min_length=1, max_length=300)
    action: str = Field(min_length=1, max_length=600)
    emotion: str = Field(min_length=1, max_length=200)
    image_prompt: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_range(self) -> _SceneDraft:
        if self.dialogue_end < self.dialogue_start:
            raise ValueError("dialogue_end must not precede dialogue_start")
        return self


class _PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenes: list[_SceneDraft] = Field(min_length=1, max_length=12)


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _json_object(text: str) -> object:
    candidate = text.strip()
    fenced = _JSON_FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as error:
        raise StoryboardValidationError("Storyboard planner returned invalid JSON") from error


def _normalize_scene_shapes(value: object) -> object:
    """Accept equivalent planner range shapes before strict validation.

    Models sometimes group the two range fields under ``dialogue_range`` and
    omit a redundant scene number.  Normalize those harmless presentation
    differences while keeping all content and the contiguous-range checks
    below strict.
    """

    if not isinstance(value, dict):
        return value
    scenes = value.get("scenes")
    if not isinstance(scenes, list):
        return value
    normalized: list[object] = []
    for index, raw_scene in enumerate(scenes, start=1):
        if not isinstance(raw_scene, dict):
            normalized.append(raw_scene)
            continue
        scene = dict(raw_scene)
        dialogue_range = scene.pop("dialogue_range", None)
        if isinstance(dialogue_range, dict):
            start = dialogue_range.get("start_line", dialogue_range.get("start"))
            end = dialogue_range.get("end_line", dialogue_range.get("end"))
            if "dialogue_start" not in scene and start is not None:
                scene["dialogue_start"] = start
            if "dialogue_end" not in scene and end is not None:
                scene["dialogue_end"] = end
        scene.setdefault("scene_number", index)
        normalized.append(scene)
    return {**value, "scenes": normalized}


def parse_storyboard_plan(
    raw: str,
    *,
    source_lines: Sequence[StoryboardSourceLine],
    characters_by_name: Mapping[str, UUID],
) -> StoryboardPlan:
    """Parse a planner response and resolve public character names to IDs."""

    try:
        draft = _PlanDraft.model_validate(_normalize_scene_shapes(_json_object(raw)))
    except ValidationError as error:
        raise StoryboardValidationError("Storyboard planner returned an invalid plan") from error

    if draft.scenes[0].dialogue_start != 1:
        raise StoryboardValidationError("Storyboard scenes must start at source line 1")

    expected_start = 1
    scenes: list[StoryboardScene] = []
    for scene in draft.scenes:
        if scene.scene_number != len(scenes) + 1:
            raise StoryboardValidationError("Scene numbers must be contiguous")
        if scene.dialogue_start != expected_start:
            raise StoryboardValidationError(
                "Storyboard scenes must cover source lines contiguously"
            )
        if scene.dialogue_end > len(source_lines):
            raise StoryboardValidationError("Storyboard scene points past the source transcript")

        entity_ids: list[UUID] = []
        for character_name in scene.characters:
            entity_id = characters_by_name.get(character_name.casefold())
            if entity_id is None:
                raise StoryboardValidationError(
                    f"Storyboard scene names unknown character {character_name!r}"
                )
            if entity_id not in entity_ids:
                entity_ids.append(entity_id)
        scenes.append(
            StoryboardScene(
                scene_number=scene.scene_number,
                dialogue_start=scene.dialogue_start,
                dialogue_end=scene.dialogue_end,
                character_entity_ids=tuple(entity_ids),
                location=scene.location,
                action=scene.action,
                emotion=scene.emotion,
                image_prompt=scene.image_prompt,
            )
        )
        expected_start = scene.dialogue_end + 1

    if expected_start != len(source_lines) + 1:
        raise StoryboardValidationError("Storyboard scenes must cover every source line")
    return StoryboardPlan(scenes=tuple(scenes))


def storyboard_planner_prompt() -> str:
    """Stable system prompt for the bounded scene segmentation call."""

    return (
        "Storyboard planner v1. Analyze only the public story context supplied by the caller. "
        "Return JSON only with a scenes array. Each scene must contain scene_number, "
        "dialogue_start, dialogue_end, characters, location, action, emotion, and image_prompt. "
        "Split the source transcript into contiguous, non-overlapping dialogue ranges covering "
        "every line exactly once. Preserve original dialogue by returning ranges, never rewrite "
        "or summarize dialogue. Use only character names present in the supplied cast. Generate "
        "one concise image_prompt per scene."
    )
