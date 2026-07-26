"""Database-independent helpers shared by storyboard routes and workers."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from story_engine.storyboard.models import CharacterVisualProfile, StoryboardSourceLine


def planner_input(
    *,
    scenario: str,
    profiles: Sequence[CharacterVisualProfile],
    source_lines: Sequence[StoryboardSourceLine],
) -> str:
    """Build bounded public context for the segmentation call."""

    cast_text = "\n".join(
        f"- {profile.name} ({profile.entity_id}): background={profile.background_story[:800]}; "
        f"visual={profile.visual_description[:500]}"
        for profile in profiles
    )
    transcript = "\n".join(
        f"{line.line_number}. {line.speaker_name or 'Unknown speaker'}: {line.text[:4_000]}"
        for line in source_lines
    )
    return (
        f"Scenario:\n{scenario[:4_000]}\n\nPublic cast:\n{cast_text}"
        f"\n\nSource transcript:\n{transcript}"
    )


def name_lookup(profiles: Sequence[CharacterVisualProfile]) -> dict[str, UUID]:
    return {profile.name.casefold(): profile.entity_id for profile in profiles}
