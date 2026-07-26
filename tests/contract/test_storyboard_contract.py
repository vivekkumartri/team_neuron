from fastapi.testclient import TestClient

from story_engine.app import create_app

client = TestClient(create_app())


def test_storyboard_creation_requires_authentication() -> None:
    response = client.post("/api/v1/chapters/00000000-0000-0000-0000-000000000000/storyboard")
    assert response.status_code == 401


def test_storyboard_asset_requires_authentication() -> None:
    response = client.get("/api/v1/storyboard-assets/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


def test_storyboard_schema_does_not_expose_image_prompt() -> None:
    schema = client.get("/openapi.json").json()
    scene_schema = schema["components"]["schemas"]["StoryboardSceneResponse"]["properties"]
    assert "image_prompt" not in scene_schema
