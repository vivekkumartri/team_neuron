"""Deterministic prompt assembly for canonical references and scene panels."""

from __future__ import annotations

from collections.abc import Sequence

from story_engine.storyboard.models import CharacterVisualProfile, StoryboardScene

STYLE_SUFFIX = (
    "simple flat comic illustration, clean line art, flat colors, consistent character "
    "appearance, medium shot, minimal background, natural expressions, landscape orientation"
)


def canonical_reference_prompt(profile: CharacterVisualProfile) -> str:
    details = "; ".join(
        value
        for value in (profile.name, profile.visual_description, profile.background_story)
        if value
    )
    return (
        f"Create a clean character reference portrait for {details}. Show one person, neutral "
        f"expression, clear facial features and clothing details. {STYLE_SUFFIX}."
    )


def scene_image_prompt(scene: StoryboardScene, profiles: Sequence[CharacterVisualProfile]) -> str:
    cast = "; ".join(
        f"{profile.name}: {profile.visual_description or 'use the supplied reference appearance'}"
        for profile in profiles
    )
    return (
        f"{scene.image_prompt.strip()} Location: {scene.location}. Action: {scene.action}. "
        f"Emotion: {scene.emotion}. Character appearance references: {cast}. {STYLE_SUFFIX}."
    )[:2_000]
