from uuid import UUID

import pytest

from story_engine.storyboard.models import StoryboardSourceLine
from story_engine.storyboard.segmentation import StoryboardValidationError, parse_storyboard_plan

MIRA = UUID("11111111-1111-1111-1111-111111111111")
ARUN = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def source_lines() -> tuple[StoryboardSourceLine, ...]:
    return (
        StoryboardSourceLine(line_number=1, speaker_name="Mira", text="The light went dark."),
        StoryboardSourceLine(
            line_number=2, speaker_name="Arun", text="Then someone wanted ships unseen."
        ),
        StoryboardSourceLine(line_number=3, speaker_name="Mira", text="Inspect the tower."),
    )


def test_plan_resolves_names_and_covers_exact_source_ranges(source_lines) -> None:
    raw = """
    {"scenes":[
      {"scene_number":1,"dialogue_start":1,"dialogue_end":2,
       "characters":["Mira","Arun"],"location":"tower","action":"investigate",
       "emotion":"tense","image_prompt":"Two people face a dark beacon."},
      {"scene_number":2,"dialogue_start":3,"dialogue_end":3,
       "characters":["Mira"],"location":"stairs","action":"climb",
       "emotion":"determined","image_prompt":"Mira climbs the stairs."}
    ]}
    """
    plan = parse_storyboard_plan(
        raw,
        source_lines=source_lines,
        characters_by_name={"mira": MIRA, "arun": ARUN},
    )
    assert plan.scenes[0].character_entity_ids == (MIRA, ARUN)
    assert (plan.scenes[0].dialogue_start, plan.scenes[-1].dialogue_end) == (1, 3)


@pytest.mark.parametrize(
    "raw",
    [
        (
            '{"scenes": [{"scene_number": 1, "dialogue_start": 1, '
            '"dialogue_end": 2, "characters": ["Mira"], "location": "tower", '
            '"action": "look", "emotion": "tense", "image_prompt": "x"}]}'
        ),
        (
            '{"scenes": [{"scene_number": 1, "dialogue_start": 1, '
            '"dialogue_end": 1, "characters": ["Unknown"], "location": "tower", '
            '"action": "look", "emotion": "tense", "image_prompt": "x"}, '
            '{"scene_number": 2, "dialogue_start": 3, "dialogue_end": 3, '
            '"characters": ["Mira"], "location": "tower", "action": "look", '
            '"emotion": "tense", "image_prompt": "x"}]}'
        ),
    ],
)
def test_invalid_ranges_or_unknown_characters_fail_closed(raw, source_lines) -> None:
    with pytest.raises(StoryboardValidationError):
        parse_storyboard_plan(
            raw,
            source_lines=source_lines,
            characters_by_name={"mira": MIRA, "arun": ARUN},
        )


def test_fenced_json_is_supported(source_lines) -> None:
    raw = """```json
    {"scenes":[{"scene_number":1,"dialogue_start":1,"dialogue_end":3,
    "characters":["Mira","Arun"],"location":"tower","action":"investigate",
    "emotion":"tense","image_prompt":"A dark tower."}]}
    ```"""
    plan = parse_storyboard_plan(
        raw,
        source_lines=source_lines,
        characters_by_name={"mira": MIRA, "arun": ARUN},
    )
    assert len(plan.scenes) == 1


def test_nested_dialogue_range_and_implicit_scene_number_are_normalized(source_lines) -> None:
    raw = """{
      "scenes": [
        {"dialogue_range": {"start_line": 1, "end_line": 2},
         "characters": ["Mira", "Arun"], "location": "tower",
         "action": "investigate", "emotion": "tense",
         "image_prompt": "Two people face a dark beacon."},
        {"dialogue_range": {"start_line": 3, "end_line": 3},
         "characters": ["Mira"], "location": "stairs",
         "action": "climb", "emotion": "determined",
         "image_prompt": "Mira climbs the stairs."}
      ]
    }"""
    plan = parse_storyboard_plan(
        raw,
        source_lines=source_lines,
        characters_by_name={"mira": MIRA, "arun": ARUN},
    )
    ranges = [
        (scene.scene_number, scene.dialogue_start, scene.dialogue_end) for scene in plan.scenes
    ]
    assert ranges == [
        (1, 1, 2),
        (2, 3, 3),
    ]
