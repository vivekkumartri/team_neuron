"""Background job tracking for multi-voice chapter narration.

Zero-shot IndicF5 synthesis of a whole chapter, one line at a time, realistically
takes several minutes — far too long to hold open a single HTTP request. This
module tracks progress with an in-memory dict (this app runs as a single
Databricks App container, so that's live for as long as the container is)
*and* mirrors every state transition to a small JSON file per chapter, so a
process restart mid-generation (e.g. `uvicorn --reload` picking up an
unrelated source change while a job is running — the most common way this
bites in local dev) is detectable instead of silently pretending nothing
ever happened: `get_status` finds the on-disk `GENERATING` marker with no
matching in-memory job and reports it as `FAILED` with an explicit
"interrupted" message (keeping whatever lines had already finished, rather
than quietly reverting to `NOT_STARTED` and losing them.

Lines are pushed out as they finish, not batched at the end: `start_job`
passes `character_audio.synthesize_script_audio` an `on_line` callback that
appends each ~3-4 second clip to the job (and persists it) the moment it's
ready, while `status` stays `GENERATING`. A poller can render/play lines
long before the whole chapter is done instead of waiting for the last line
to know about the first one.

Once every line is done, all of them (in script order — one chunk per
character turn) are joined into a single `combined_audio_bytes` track via
`character_audio.concatenate_wav_clips`, so a chapter is available both as
individual per-character chunks (for the chunk-by-chunk UI) and as one
continuous file.

A finished (`READY`) job's audio is also persisted, so once narration has
actually completed once, a later restart still serves it instantly instead
of regenerating from scratch.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid import UUID

from story_engine.agents.indicf5_provider import IndicF5Provider
from story_engine.agents.provider import ModelProvider, ModelProviderError
from story_engine.services.character_audio import (
    CharacterAudioError,
    CharacterAudioLine,
    concatenate_wav_clips,
    synthesize_script_audio,
)
from story_engine.services.script_parser import ScriptLineKind
from story_engine.services.voice_casting import VoiceCastingError
from story_engine.services.voice_uploads import UploadedVoice

# Not a promise, just a UI hint set from observed IndicF5 zero-shot latency
# per line at the default `nfe_step` on a typical chapter's line count.
ESTIMATED_SECONDS = 5 * 60

_JOBS_DIR = Path(__file__).resolve().parents[3] / "indicf5_tts" / "outputs" / "narration_jobs"

_INTERRUPTED_MESSAGE = (
    "Narration generation was interrupted (the server restarted while it was "
    "still running). Nothing was lost from your story — just try generating "
    "narration again."
)


class NarrationStatus(str, Enum):
    NOT_STARTED = "not_started"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


@dataclass
class NarrationJob:
    status: NarrationStatus
    started_at: float | None = None
    lines: list[CharacterAudioLine] = field(default_factory=list)
    error: str | None = None
    # Only set once status is READY — every line's clip joined into one
    # continuous track, in script order.
    combined_audio_bytes: bytes | None = None


_jobs: dict[UUID, NarrationJob] = {}
_lock = threading.Lock()


def _job_path(chapter_id: UUID) -> Path:
    _JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return _JOBS_DIR / f"{chapter_id}.json"


def _persist(chapter_id: UUID, job: NarrationJob) -> None:
    """Best-effort mirror to disk; a write failure must never break the job itself."""

    try:
        payload = {
            "status": job.status.value,
            "error": job.error,
            "lines": [
                {
                    "scene_index": line.scene_index,
                    "kind": line.kind.value,
                    "speaker": line.speaker,
                    "text": line.text,
                    "voice_id": line.voice_id,
                    "audio_base64": base64.b64encode(line.audio_bytes).decode("ascii"),
                }
                for line in job.lines
            ],
            "combined_audio_base64": (
                base64.b64encode(job.combined_audio_bytes).decode("ascii")
                if job.combined_audio_bytes is not None
                else None
            ),
        }
        _job_path(chapter_id).write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def _load_from_disk(chapter_id: UUID) -> NarrationJob | None:
    path = _job_path(chapter_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    status = payload.get("status")
    lines = [
        CharacterAudioLine(
            scene_index=item["scene_index"],
            kind=ScriptLineKind(item["kind"]),
            speaker=item["speaker"],
            text=item["text"],
            voice_id=item["voice_id"],
            audio_bytes=base64.b64decode(item["audio_base64"]),
        )
        for item in payload.get("lines", [])
    ]
    if status == NarrationStatus.GENERATING.value:
        # A GENERATING marker with nothing live in `_jobs` means the process
        # that was running this job is gone — it never got to write a final
        # READY/FAILED result, so treat it as interrupted rather than
        # resurrecting a job no thread is actually running anymore. Whatever
        # lines it had already pushed out before dying are kept, not thrown
        # away — they're valid, finished audio regardless of how the job as
        # a whole ended.
        return NarrationJob(status=NarrationStatus.FAILED, error=_INTERRUPTED_MESSAGE, lines=lines)
    if status == NarrationStatus.READY.value:
        combined_b64 = payload.get("combined_audio_base64")
        return NarrationJob(
            status=NarrationStatus.READY,
            lines=lines,
            combined_audio_bytes=base64.b64decode(combined_b64) if combined_b64 else None,
        )
    if status == NarrationStatus.FAILED.value:
        return NarrationJob(status=NarrationStatus.FAILED, error=payload.get("error"), lines=lines)
    return None


def get_status(chapter_id: UUID) -> NarrationJob:
    with _lock:
        job = _jobs.get(chapter_id)
    if job is not None:
        return job

    from_disk = _load_from_disk(chapter_id)
    if from_disk is None:
        return NarrationJob(status=NarrationStatus.NOT_STARTED)
    # Cache the recovered (or interrupted) result in memory too, so we don't
    # re-read and re-decode the file on every subsequent poll.
    with _lock:
        _jobs.setdefault(chapter_id, from_disk)
    return from_disk


def start_job(
    *,
    chapter_id: UUID,
    raw_text: str,
    provider: ModelProvider,
    casting_model: str,
    tts: IndicF5Provider,
    voice_overrides: dict[str, UploadedVoice],
) -> NarrationJob:
    """Start generation if nothing is already running/ready for this chapter."""

    current = get_status(chapter_id)
    if current.status in (NarrationStatus.GENERATING, NarrationStatus.READY):
        return current

    job = NarrationJob(status=NarrationStatus.GENERATING, started_at=time.monotonic())
    with _lock:
        _jobs[chapter_id] = job
    _persist(chapter_id, job)

    def _on_line(line: CharacterAudioLine) -> None:
        # Mutate the same job object every poller already holds a reference
        # to via `get_status` — a new line becomes visible the instant it's
        # appended, not only once the whole chapter finishes.
        with _lock:
            job.lines.append(line)
        _persist(chapter_id, job)

    def _run() -> None:
        try:
            synthesize_script_audio(
                raw_text=raw_text,
                provider=provider,
                casting_model=casting_model,
                tts=tts,
                voice_overrides=voice_overrides,
                on_line=_on_line,
            )
            # Join every line's chunk (in script order) into one continuous
            # track now that they're all done. A join failure (e.g. a
            # mismatched clip format) shouldn't discard otherwise-good
            # per-line audio — the chunk-by-chunk UI still works without it
            # — so this degrades to READY-without-a-combined-track rather
            # than failing the whole job.
            combined: bytes | None
            try:
                combined = concatenate_wav_clips([line.audio_bytes for line in job.lines])
            except CharacterAudioError:
                combined = None
            with _lock:
                job.status = NarrationStatus.READY
                job.combined_audio_bytes = combined
        except (CharacterAudioError, VoiceCastingError, ModelProviderError) as error:
            with _lock:
                job.status = NarrationStatus.FAILED
                job.error = str(error)
        except Exception:  # noqa: BLE001 - a dead background thread must still report FAILED
            with _lock:
                job.status = NarrationStatus.FAILED
                job.error = "Narration generation failed unexpectedly."
        _persist(chapter_id, job)

    threading.Thread(target=_run, daemon=True).start()
    return job
