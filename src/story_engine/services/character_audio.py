"""Multi-voice audio generation for a script: one IndicF5 voice per character.

Orchestrates `services/script_parser.py` (segment raw text into speaker-tagged
lines), `services/voice_casting.py` (assign each character a reference
voice from the curated library), `services/voice_uploads.py` (a character's
own author-uploaded reference clip, which always wins over the auto-cast
library voice when present), and `agents/indicf5_provider.py` (synthesize
each line). Action/narration lines are voiced with a fixed narrator entry
from the voice library rather than being skipped, so the output is a
complete audio reading of the scene, not dialogue-only.
"""

from __future__ import annotations

import base64
import io
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from story_engine.agents.indicf5_provider import IndicF5Provider
from story_engine.agents.provider import ModelProvider, ModelProviderError
from story_engine.services.script_parser import ScriptLine, ScriptLineKind, parse_script, speaking_characters
from story_engine.services.voice_casting import (
    VoiceArchetype,
    VoiceLibraryEntry,
    cast_voices,
    load_voice_library,
    match_voice,
)
from story_engine.services.voice_uploads import UploadedVoice

_TTS_ROOT = Path(__file__).resolve().parents[3] / "indicf5_tts"
_NARRATOR_VOICE_ID = "narrator_female_warm"


@dataclass(frozen=True)
class CharacterAudioLine:
    scene_index: int
    kind: ScriptLineKind
    speaker: str | None
    text: str
    voice_id: str
    audio_bytes: bytes


class CharacterAudioError(RuntimeError):
    """Raised when the script has no narratable content to synthesize."""


def concatenate_wav_clips(clips: list[bytes]) -> bytes:
    """Join per-line WAV clips (each character's chunk, in script order) into one track.

    Every clip comes from the same IndicF5 server (`agents/indicf5_provider.py`),
    which always renders 24kHz mono 16-bit PCM WAV, so this only needs plain
    stdlib `wave` concatenation — no resampling/mixing library required. Raises
    `CharacterAudioError` if a clip doesn't match the first clip's format,
    since silently concatenating mismatched PCM would produce corrupt/garbled
    audio rather than a clear failure.
    """

    if not clips:
        raise CharacterAudioError("No audio clips to join.")

    try:
        with wave.open(io.BytesIO(clips[0]), "rb") as first_reader:
            params = first_reader.getparams()
            frames: list[bytes] = [first_reader.readframes(first_reader.getnframes())]

        for index, clip in enumerate(clips[1:], start=1):
            with wave.open(io.BytesIO(clip), "rb") as reader:
                clip_params = reader.getparams()
                if clip_params[:3] != params[:3]:  # nchannels, sampwidth, framerate
                    raise CharacterAudioError(
                        f"Clip {index} has a different audio format than the first clip; "
                        "cannot join into one track."
                    )
                frames.append(reader.readframes(reader.getnframes()))
    except wave.Error as error:
        raise CharacterAudioError(f"A clip was not valid WAV audio: {error}") from error

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(params.nchannels)
        writer.setsampwidth(params.sampwidth)
        writer.setframerate(params.framerate)
        for chunk in frames:
            writer.writeframes(chunk)
    return buffer.getvalue()


def _ref_audio_base64(entry: VoiceLibraryEntry) -> str:
    clip_path = _TTS_ROOT / entry.file
    return base64.b64encode(clip_path.read_bytes()).decode("ascii")


def _narrator_voice(library: list[VoiceLibraryEntry]) -> VoiceLibraryEntry:
    for entry in library:
        if entry.id == _NARRATOR_VOICE_ID:
            return entry
    return library[0]


def _resolve_reference(
    *, upload: UploadedVoice | None, entry: VoiceLibraryEntry
) -> tuple[str, str, str]:
    """Return (ref_audio_base64, ref_text, voice_id) for one line, upload wins."""

    if upload is not None:
        return (
            base64.b64encode(upload.file_path.read_bytes()).decode("ascii"),
            upload.ref_text,
            f"uploaded:{upload.character_name}",
        )
    return _ref_audio_base64(entry), entry.ref_text or "", entry.id


def synthesize_script_audio(
    *,
    raw_text: str,
    provider: ModelProvider,
    casting_model: str,
    tts: IndicF5Provider,
    # IndicF5's diffusion step count: lower = faster, lower quality. Default
    # dropped from 32 to 4 — on this local (non-CUDA) setup, 32 was taking
    # 25-70+ seconds per line even for short lines, which is what was making
    # a whole chapter take many minutes. 4 trades audio fidelity for speed,
    # explicitly requested for now to get end-to-end generation fast enough
    # to actually test/demo.
    nfe_step: int = 4,
    voice_overrides: dict[str, UploadedVoice] | None = None,
    on_line: Callable[[CharacterAudioLine], None] | None = None,
) -> list[CharacterAudioLine]:
    """Parse `raw_text`, cast a voice per speaking character, synthesize every line.

    `voice_overrides` maps a character name to an author-uploaded reference
    clip (`services/voice_uploads.py`); any character present there is never
    sent through the LLM auto-casting step at all — their voice is already
    decided. Every other speaking character still gets a library voice via
    `services/voice_casting.py`.

    `on_line`, if given, is called synchronously right after each line's
    clip finishes synthesizing (not batched at the end) — a whole chapter
    can take minutes, and a caller (`services/narration_jobs.py`) uses this
    to push each 3-4 second clip out to the client as soon as it exists,
    instead of making an author wait for every line before hearing any of
    them.

    Raises `CharacterAudioError` if the script has no lines at all.
    Individual line synthesis failures are not swallowed — a
    `ModelProviderError` from the TTS backend propagates, since a caller
    needs to know audio generation actually failed rather than silently
    getting a partial track.
    """

    lines = parse_script(raw_text)
    if not lines:
        raise CharacterAudioError("The script had no narratable content.")

    overrides = voice_overrides or {}
    library = load_voice_library()
    narrator_voice = _narrator_voice(library)

    character_names = speaking_characters(lines)
    characters_needing_cast = [name for name in character_names if name not in overrides]
    voice_map = (
        cast_voices(
            provider=provider,
            model=casting_model,
            scene_text=raw_text,
            character_names=characters_needing_cast,
        )
        if characters_needing_cast
        else {}
    )

    results: list[CharacterAudioLine] = []
    for line in lines:
        upload: UploadedVoice | None = None
        if line.kind == ScriptLineKind.DIALOGUE and line.speaker:
            upload = overrides.get(line.speaker)
            entry = voice_map.get(line.speaker) or match_voice(
                VoiceArchetype(name=line.speaker, gender="neutral", age_group="adult", tone=""),
                library,
            )
        else:
            entry = narrator_voice

        ref_audio_b64, ref_text, voice_id = _resolve_reference(upload=upload, entry=entry)

        try:
            audio_bytes = tts.synthesize_speech(
                text=line.text,
                ref_audio_base64=ref_audio_b64,
                ref_text=ref_text,
                nfe_step=nfe_step,
            )
        except ModelProviderError:
            raise

        audio_line = CharacterAudioLine(
            scene_index=line.scene_index,
            kind=line.kind,
            speaker=line.speaker,
            text=line.text,
            voice_id=voice_id,
            audio_bytes=audio_bytes,
        )
        results.append(audio_line)
        if on_line is not None:
            on_line(audio_line)

    return results
