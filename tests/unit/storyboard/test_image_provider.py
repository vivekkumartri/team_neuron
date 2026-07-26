import base64
import json
from collections.abc import Iterator
from contextlib import contextmanager

from story_engine.storyboard.image_provider import OpenAIImageProvider


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_generation_request_uses_generation_endpoint_without_references(monkeypatch) -> None:
    captured: dict[str, object] = {}

    @contextmanager
    def fake_urlopen(request, timeout: float) -> Iterator[_Response]:
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        yield _Response({"data": [{"b64_json": base64.b64encode(b"panel").decode()}]})

    monkeypatch.setattr("story_engine.storyboard.image_provider.urlopen", fake_urlopen)
    image = OpenAIImageProvider(api_key="test-key").generate(
        prompt="A lighthouse",
        model="gpt-image-2",
        reference_images=(),
        quality="low",
    )
    assert image == b"panel"
    assert captured["url"] == "https://api.openai.com/v1/images/generations"
    assert captured["body"]["model"] == "gpt-image-2"


def test_edit_request_contains_the_same_reference_image_bytes(monkeypatch) -> None:
    captured: dict[str, object] = {}

    @contextmanager
    def fake_urlopen(request, timeout: float) -> Iterator[_Response]:
        captured["url"] = request.full_url
        captured["body"] = request.data
        yield _Response({"data": [{"b64_json": base64.b64encode(b"panel").decode()}]})

    monkeypatch.setattr("story_engine.storyboard.image_provider.urlopen", fake_urlopen)
    OpenAIImageProvider(api_key="test-key").generate(
        prompt="Mira and Arun",
        model="gpt-image-2",
        reference_images=(("image/png", b"mira-ref"), ("image/jpeg", b"arun-ref")),
        quality="low",
    )
    body = captured["body"]
    assert captured["url"] == "https://api.openai.com/v1/images/edits"
    assert b"mira-ref" in body and b"arun-ref" in body
    assert b"reference-0.png" in body and b"reference-1.jpg" in body
