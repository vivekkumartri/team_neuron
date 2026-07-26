"""Generate 5 male + 5 female local reference voices for IndicF5 casting.

macOS-only local-dev tool: uses the built-in `say` command (Apple's own
system TTS voices, licensed for on-device use — not a real/identifiable
person, see `services/voice_casting.py`'s module docstring for why that
distinction matters here) to synthesize a short clip per voice, converts it
to a 24kHz mono WAV with `afconvert` (also macOS built-in) into
`indicf5_tts/prompts/`, and appends verified entries to
`indicf5_tts/voice_library.json` — verified because we generated the audio
ourselves, so the reference text is known exactly rather than guessed via
transcription.

These are the automatic-fallback voices `services/voice_casting.py` picks
between whenever a story's character has no author-uploaded voice
(`services/voice_uploads.py`) — five men, five women, so casting always has
a real option for both, independent of anything a user chooses to upload.

Usage (from repo root):
    python scripts/generate_local_reference_voices.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

_TTS_ROOT = Path(__file__).resolve().parents[1] / "indicf5_tts"
_PROMPTS_DIR = _TTS_ROOT / "prompts"
_LIBRARY_PATH = _TTS_ROOT / "voice_library.json"

_REFERENCE_SENTENCE = (
    "This is a short reference recording used to clone this character's voice for narration."
)

# (library id, macOS `say` voice name, gender, age_group, tone)
_VOICES: list[tuple[str, str, str, str, str]] = [
    ("female_local_samantha", "Samantha", "female", "adult", "warm, clear"),
    ("female_local_karen", "Karen", "female", "adult", "bright, friendly"),
    ("female_local_kathy", "Kathy", "female", "young", "energetic, light"),
    ("female_local_moira", "Moira", "female", "adult", "measured, soft"),
    ("female_local_tara", "Tara", "female", "young", "warm, gentle"),
    ("male_local_daniel", "Daniel", "male", "adult", "measured, authoritative"),
    ("male_local_aman", "Aman", "male", "adult", "warm, steady"),
    ("male_local_rishi", "Rishi", "male", "young", "bright, energetic"),
    ("male_local_fred", "Fred", "male", "elder", "gravelly, quirky"),
    ("male_local_ralph", "Ralph", "male", "elder", "stern, gruff"),
]


def _synthesize(voice_name: str, out_path: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".aiff") as aiff:
        subprocess.run(
            ["say", "-v", voice_name, "-o", aiff.name, _REFERENCE_SENTENCE],
            check=True,
        )
        subprocess.run(
            [
                "afconvert",
                "-f",
                "WAVE",
                "-d",
                "LEI16@24000",
                "-c",
                "1",
                aiff.name,
                str(out_path),
            ],
            check=True,
        )


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("This generator uses macOS's `say`/`afconvert` — only runs on macOS.")

    _PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    library = json.loads(_LIBRARY_PATH.read_text(encoding="utf-8"))
    existing_ids = {voice["id"] for voice in library["voices"]}

    for voice_id, say_voice, gender, age_group, tone in _VOICES:
        filename = f"{voice_id}.wav"
        out_path = _PROMPTS_DIR / filename
        print(f"Synthesizing {voice_id} ({say_voice})...")
        _synthesize(say_voice, out_path)

        entry = {
            "id": voice_id,
            "file": f"prompts/{filename}",
            "gender": gender,
            "age_group": age_group,
            "tone": tone,
            "ref_text": _REFERENCE_SENTENCE,
        }
        if voice_id in existing_ids:
            library["voices"] = [
                entry if v["id"] == voice_id else v for v in library["voices"]
            ]
        else:
            library["voices"].append(entry)

    _LIBRARY_PATH.write_text(
        json.dumps(library, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Updated {_LIBRARY_PATH} with {len(_VOICES)} local voices.")


if __name__ == "__main__":
    main()
