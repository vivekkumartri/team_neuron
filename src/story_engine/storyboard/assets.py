"""Validation and hashing for author-supplied image data."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass

MAX_REFERENCE_IMAGE_BYTES = 8 * 1024 * 1024
_DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$")


class ImageDataError(ValueError):
    """The submitted image is unsupported or too large."""


@dataclass(frozen=True)
class ImageAsset:
    mime_type: str
    content: bytes
    sha256: str


def decode_image_data_url(value: str) -> ImageAsset:
    """Decode a bounded PNG/JPEG/WebP data URL without accepting SVG/script data."""

    match = _DATA_URL.fullmatch(value.strip())
    if match is None:
        raise ImageDataError("Character photo must be a PNG, JPEG, or WebP data URL")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ImageDataError("Character photo is not valid base64") from error
    if not content:
        raise ImageDataError("Character photo cannot be empty")
    if len(content) > MAX_REFERENCE_IMAGE_BYTES:
        raise ImageDataError("Character photo is too large")
    return ImageAsset(
        mime_type=match.group(1),
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )
