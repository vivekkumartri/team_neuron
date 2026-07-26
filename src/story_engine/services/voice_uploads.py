"""Per-user, per-character uploaded reference voices for IndicF5 cloning.

This is the consented path: an author uploads their OWN (or otherwise
rights-cleared) short voice clip for a specific character, together with its
exact transcript, and that clip is used as the IndicF5 zero-shot reference
for every line that character speaks — no real/named public figure's audio
is ever fetched or guessed at (see `services/voice_casting.py`'s module
docstring for why).

Storage is a plain per-user directory under `indicf5_tts/ref_uploads/`, with
one small JSON metadata sidecar per user. This is a prototype-grade store
(no DB table, no multi-instance coordination) — acceptable here because it
is scoped to a single Databricks App container's local disk and every read
is keyed by the authenticated user's own id.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

_UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "indicf5_tts" / "ref_uploads"

_ALLOWED_CONTENT_TYPES = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
}

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # generous for a few seconds-to-tens-of-seconds clip
_MAX_CHARACTER_NAME_CHARS = 80


class VoiceUploadError(ValueError):
    """Raised for a rejected upload: bad content type, too large, or bad name."""


@dataclass(frozen=True)
class UploadedVoice:
    character_name: str
    file_path: Path
    ref_text: str
    content_type: str


def _user_dir(user_id: str) -> Path:
    # user_id is always a UUID string from `AuthenticatedUser.id`, never
    # caller-controlled free text, so it is safe to use directly as a path
    # segment without further sanitization.
    directory = _UPLOAD_ROOT / user_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _metadata_path(user_id: str) -> Path:
    return _user_dir(user_id) / "metadata.json"


def _load_metadata(user_id: str) -> dict[str, dict[str, str]]:
    path = _metadata_path(user_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_metadata(user_id: str, metadata: dict[str, dict[str, str]]) -> None:
    _metadata_path(user_id).write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def save_character_voice(
    *,
    user_id: str,
    character_name: str,
    audio_bytes: bytes,
    content_type: str,
    ref_text: str,
) -> UploadedVoice:
    """Persist an uploaded reference clip for one character, replacing any prior upload."""

    name = character_name.strip()
    if not name or len(name) > _MAX_CHARACTER_NAME_CHARS:
        raise VoiceUploadError("Character name must be 1-80 characters.")
    if not ref_text.strip():
        raise VoiceUploadError("An exact transcript of the uploaded clip is required.")
    if not audio_bytes:
        raise VoiceUploadError("The uploaded audio file was empty.")
    if len(audio_bytes) > _MAX_UPLOAD_BYTES:
        raise VoiceUploadError("The uploaded audio file is too large (max 15 MB).")
    extension = _ALLOWED_CONTENT_TYPES.get(content_type.split(";")[0].strip().lower())
    if extension is None:
        raise VoiceUploadError(f"Unsupported audio type: {content_type}")

    metadata = _load_metadata(user_id)
    # Replace a prior upload for the same character name (case-sensitive —
    # character names are matched case-sensitively against script speaker
    # cues elsewhere in this feature).
    previous = metadata.get(name)
    if previous:
        old_path = _user_dir(user_id) / previous["filename"]
        old_path.unlink(missing_ok=True)

    filename = f"{uuid.uuid4().hex}.{extension}"
    file_path = _user_dir(user_id) / filename
    file_path.write_bytes(audio_bytes)

    metadata[name] = {
        "filename": filename,
        "ref_text": ref_text.strip(),
        "content_type": content_type,
    }
    _save_metadata(user_id, metadata)

    return UploadedVoice(
        character_name=name, file_path=file_path, ref_text=ref_text.strip(), content_type=content_type
    )


def list_character_voices(user_id: str) -> dict[str, UploadedVoice]:
    metadata = _load_metadata(user_id)
    voices: dict[str, UploadedVoice] = {}
    for name, entry in metadata.items():
        file_path = _user_dir(user_id) / entry["filename"]
        if not file_path.exists():
            continue
        voices[name] = UploadedVoice(
            character_name=name,
            file_path=file_path,
            ref_text=entry["ref_text"],
            content_type=entry["content_type"],
        )
    return voices


def delete_character_voice(*, user_id: str, character_name: str) -> bool:
    metadata = _load_metadata(user_id)
    entry = metadata.pop(character_name, None)
    if entry is None:
        return False
    (_user_dir(user_id) / entry["filename"]).unlink(missing_ok=True)
    _save_metadata(user_id, metadata)
    return True

