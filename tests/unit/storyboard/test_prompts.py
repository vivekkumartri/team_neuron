from uuid import UUID

from story_engine.storyboard.models import CharacterVisualProfile, StoryboardScene
from story_engine.storyboard.prompts import canonical_reference_prompt, scene_image_prompt


def test_canonical_prompt_contains_public_visual_context_and_fixed_style() -> None:
    profile = CharacterVisualProfile(
        entity_id=UUID("11111111-1111-1111-1111-111111111111"),
        name="Mira",
        background_story="A lighthouse keeper.",
        visual_description="navy coat and brass lantern",
    )
    prompt = canonical_reference_prompt(profile)
    assert "Mira" in prompt
    assert "navy coat" in prompt
    assert "consistent character appearance" in prompt


def test_scene_prompt_includes_all_referenced_characters() -> None:
    scene = StoryboardScene(
        scene_number=1,
        dialogue_start=1,
        dialogue_end=2,
        character_entity_ids=(
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ),
        location="tower",
        action="investigate the dark beacon",
        emotion="tense",
        image_prompt="Two people face the dark beacon.",
    )
    profiles = [
        CharacterVisualProfile(
            entity_id=scene.character_entity_ids[0], name="Mira", visual_description="navy coat"
        ),
        CharacterVisualProfile(
            entity_id=scene.character_entity_ids[1], name="Arun", visual_description="green jacket"
        ),
    ]
    prompt = scene_image_prompt(scene, profiles)
    assert "Mira" in prompt and "Arun" in prompt
    assert "landscape orientation" in prompt
