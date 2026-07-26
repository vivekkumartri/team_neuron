"""Build a stable, lossless source transcript from published chapter rows."""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple
from uuid import UUID

from story_engine.storyboard.models import StoryboardSourceLine


class RawDialogue(NamedTuple):
    speaker_entity_id: UUID | None
    speaker_name: str | None
    text: str


class RawScene(NamedTuple):
    summary: str
    dialogue: tuple[RawDialogue, ...]


def build_transcript(scenes: Iterable[RawScene]) -> tuple[StoryboardSourceLine, ...]:
    """Return source lines in chapter order without rewriting their text.

    New chapters should use the `dialogue` rows. Older chapters in this
    repository can contain a single screenplay summary with no dialogue rows;
    those are split only at existing line/paragraph boundaries and retain the
    complete original text with no invented speaker labels.
    """

    lines: list[StoryboardSourceLine] = []
    for scene in scenes:
        if scene.dialogue:
            for dialogue_line in scene.dialogue:
                if dialogue_line.text.strip():
                    lines.append(
                        StoryboardSourceLine(
                            line_number=len(lines) + 1,
                            speaker_entity_id=dialogue_line.speaker_entity_id,
                            speaker_name=dialogue_line.speaker_name,
                            text=dialogue_line.text,
                        )
                    )
            continue

        for screenplay_line in scene.summary.splitlines():
            if screenplay_line.strip():
                lines.append(StoryboardSourceLine(line_number=len(lines) + 1, text=screenplay_line))

    if not lines:
        raise ValueError("A chapter must contain source dialogue or screenplay text")
    return tuple(lines)
