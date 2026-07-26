from uuid import UUID

import pytest

from story_engine.storyboard.transcript import RawDialogue, RawScene, build_transcript


def test_transcript_preserves_dialogue_text_and_assigns_stable_numbers() -> None:
    entity_id = UUID("11111111-1111-1111-1111-111111111111")
    lines = build_transcript(
        [
            RawScene(
                "unused summary",
                (RawDialogue(entity_id, "Mira", "The light went dark."),),
            ),
            RawScene(
                "unused summary",
                (RawDialogue(None, None, "We should inspect the tower."),),
            ),
        ]
    )
    assert [line.line_number for line in lines] == [1, 2]
    assert lines[0].text == "The light went dark."
    assert lines[0].speaker_name == "Mira"


def test_legacy_screenplay_fallback_keeps_existing_lines_without_inventing_speakers() -> None:
    lines = build_transcript([RawScene("Mira: The light went dark.\nArun: We should leave.", ())])
    assert [line.text for line in lines] == ["Mira: The light went dark.", "Arun: We should leave."]
    assert all(line.speaker_name is None for line in lines)


def test_empty_chapter_is_rejected() -> None:
    with pytest.raises(ValueError, match="source dialogue"):
        build_transcript([RawScene("", ())])
