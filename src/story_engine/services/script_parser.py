"""Parses raw screenplay-style story text into speaker-tagged lines.

Handles scripts shaped like `docs`/author-pasted Telugu/Hindi/English scenes:
a scene heading line (e.g. "లోపల — టీ దుకాణం — సాయంత్రం"), then alternating
blocks of a bare character-name line followed by their dialogue, interleaved
with unattributed action/narration paragraphs. This is deliberately a plain
heuristic parser (no LLM call) — it only segments text that a human already
wrote, it does not generate anything, so it does not need to go through
`security/prompt_safety.py`'s untrusted-data boundary the way LLM-facing
services do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ScriptLineKind(str, Enum):
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    DIALOGUE = "dialogue"


@dataclass(frozen=True)
class ScriptLine:
    """One narratable unit: either a scene heading, an action beat, or dialogue."""

    kind: ScriptLineKind
    text: str
    scene_index: int
    speaker: str | None = None


# A scene heading is a short line that is mostly em/en-dash-separated
# fragments (e.g. "INT. TEA STALL - EVENING" / "లోపల — టీ దుకాణం — సాయంత్రం")
# and contains no sentence-ending punctuation of its own.
_SCENE_HEADING_RE = re.compile(r"^[^.!?]{1,80}[—\-–][^.!?]{1,80}$")

# A speaker cue line: short (a name, not a sentence), no trailing sentence
# punctuation, and not itself a scene heading.
_MAX_SPEAKER_NAME_CHARS = 40
_SENTENCE_END_CHARS = ".!?…।"


def _looks_like_scene_heading(line: str) -> bool:
    return bool(_SCENE_HEADING_RE.match(line.strip()))


def _looks_like_speaker_cue(line: str, known_speakers: set[str]) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_SPEAKER_NAME_CHARS:
        return False
    if stripped[-1] in _SENTENCE_END_CHARS:
        return False
    if _looks_like_scene_heading(stripped):
        return False
    # A comma-free, short, title-ish line is very likely a name — but the
    # strongest signal for a script we've already seen once is that this
    # exact line recurred as a speaker before.
    if stripped in known_speakers:
        return True
    word_count = len(stripped.split())
    return word_count <= 4 and "," not in stripped


def parse_script(raw_text: str) -> list[ScriptLine]:
    """Split raw screenplay text into scene/action/dialogue units, in order.

    Blank lines are separators only; consecutive non-blank lines belonging to
    the same dialogue block are joined with a space. A speaker cue applies to
    every dialogue paragraph until the next speaker cue, scene heading, or
    blank-separated action paragraph reasserts a different attribution.
    """

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw_text.strip()) if p.strip()]

    lines: list[ScriptLine] = []
    scene_index = -1
    known_speakers: set[str] = set()
    pending_speaker: str | None = None

    for paragraph in paragraphs:
        para_lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not para_lines:
            continue

        if len(para_lines) == 1 and _looks_like_scene_heading(para_lines[0]):
            scene_index += 1
            lines.append(
                ScriptLine(kind=ScriptLineKind.SCENE_HEADING, text=para_lines[0], scene_index=max(scene_index, 0))
            )
            pending_speaker = None
            continue

        if scene_index < 0:
            scene_index = 0

        if len(para_lines) >= 1 and _looks_like_speaker_cue(para_lines[0], known_speakers):
            speaker = para_lines[0]
            known_speakers.add(speaker)
            dialogue_text = " ".join(para_lines[1:]).strip()
            pending_speaker = speaker
            if dialogue_text:
                lines.append(
                    ScriptLine(
                        kind=ScriptLineKind.DIALOGUE,
                        text=dialogue_text,
                        scene_index=scene_index,
                        speaker=speaker,
                    )
                )
            continue

        # Not a scene heading, not a new speaker cue: either a continuation
        # of the previous speaker's dialogue (short, unattributed follow-up
        # inside the same block) or an action/narration paragraph. We treat
        # it as narration by default, which matches how this format is
        # written above (attribution lines are their own paragraph).
        lines.append(
            ScriptLine(
                kind=ScriptLineKind.ACTION,
                text=" ".join(para_lines),
                scene_index=scene_index,
            )
        )
        pending_speaker = None

    return lines


def speaking_characters(lines: list[ScriptLine]) -> list[str]:
    """Unique speaker names, in first-appearance order."""

    seen: list[str] = []
    for line in lines:
        if line.kind == ScriptLineKind.DIALOGUE and line.speaker and line.speaker not in seen:
            seen.append(line.speaker)
    return seen
