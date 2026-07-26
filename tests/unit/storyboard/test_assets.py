import base64

import pytest

from story_engine.storyboard.assets import ImageDataError, decode_image_data_url


def test_decode_image_data_url_returns_bounded_asset_metadata() -> None:
    raw = b"not-a-real-png-but-a-valid-fixture-payload"
    value = f"data:image/png;base64,{base64.b64encode(raw).decode()}"
    asset = decode_image_data_url(value)
    assert asset.mime_type == "image/png"
    assert asset.content == raw
    assert len(asset.sha256) == 64


@pytest.mark.parametrize(
    "value", ["", "data:image/svg+xml;base64,PHN2Zy8+", "data:image/png;base64,!"]
)
def test_decode_rejects_unsupported_or_invalid_data_urls(value: str) -> None:
    with pytest.raises(ImageDataError):
        decode_image_data_url(value)
