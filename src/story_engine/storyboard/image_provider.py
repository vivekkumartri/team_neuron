"""OpenAI image generation adapter and a provider protocol for tests."""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from collections.abc import Sequence
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from story_engine.agents.provider import ModelProviderError, _openai_error_summary


class ImageProvider(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        model: str,
        reference_images: Sequence[tuple[str, bytes]],
        quality: str,
    ) -> bytes: ...


class OpenAIImageProvider:
    """Server-only adapter for one image per storyboard scene.

    With no references it uses `/images/generations` to create a canonical
    character reference. With references it uses `/images/edits`, passing the
    previously stored character assets back to the model. The returned bytes
    are persisted by the storyboard worker before the API exposes them.
    """

    def __init__(self, *, api_key: str, timeout_seconds: float = 180.0) -> None:
        if not api_key:
            raise ValueError("An OpenAI API key is required")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        reference_images: Sequence[tuple[str, bytes]],
        quality: str,
    ) -> bytes:
        if reference_images:
            body, content_type = self._multipart_body(
                prompt=prompt,
                model=model,
                quality=quality,
                reference_images=reference_images,
            )
            request = Request(
                "https://api.openai.com/v1/images/edits",
                data=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": content_type,
                },
                method="POST",
            )
        else:
            payload = json.dumps(
                {
                    "model": model,
                    "prompt": prompt,
                    "n": 1,
                    "size": "1536x1024",
                    "quality": quality,
                    "output_format": "png",
                }
            ).encode("utf-8")
            request = Request(
                "https://api.openai.com/v1/images/generations",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise ModelProviderError(
                f"OpenAI image request failed ({_openai_error_summary(error)})"
            ) from error
        except URLError as error:
            raise ModelProviderError("OpenAI image service is unreachable") from error
        except TimeoutError as error:
            raise ModelProviderError("OpenAI image request timed out") from error
        except OSError as error:
            raise ModelProviderError("OpenAI image connection failed") from error
        except json.JSONDecodeError as error:
            raise ModelProviderError("OpenAI image service returned invalid JSON") from error

        try:
            encoded = body["data"][0]["b64_json"]
            image = base64.b64decode(encoded, validate=True)
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error) as error:
            raise ModelProviderError("OpenAI image service returned no image") from error
        if not image:
            raise ModelProviderError("OpenAI image service returned an empty image")
        return image

    @staticmethod
    def _multipart_body(
        *,
        prompt: str,
        model: str,
        quality: str,
        reference_images: Sequence[tuple[str, bytes]],
    ) -> tuple[bytes, str]:
        boundary = f"----story-engine-{secrets.token_hex(16)}"
        chunks: list[bytes] = []

        def field(name: str, value: str) -> None:
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    value.encode(),
                    b"\r\n",
                ]
            )

        field("model", model)
        field("prompt", prompt)
        field("n", "1")
        field("size", "1536x1024")
        field("quality", quality)
        field("output_format", "png")
        for index, (mime_type, image) in enumerate(reference_images):
            extension = mime_type.split("/", 1)[-1].replace("jpeg", "jpg")
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    (
                        'Content-Disposition: form-data; name="image[]"; '
                        f'filename="reference-{index}.{extension}"\r\n'
                    ).encode(),
                    f"Content-Type: {mime_type}\r\n\r\n".encode(),
                    image,
                    b"\r\n",
                ]
            )
        chunks.append(f"--{boundary}--\r\n".encode())
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
