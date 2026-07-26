"""One-off: fill in missing `ref_text` entries in indicf5_tts/voice_library.json.

IndicF5 zero-shot cloning needs the EXACT transcript of each reference clip,
so rather than guessing/fabricating those transcripts, this transcribes each
`ref_text: null` entry with the same Whisper adapter the live transcription
route already uses (`story_engine.agents.voice_provider.OpenAIVoiceProvider`),
then writes the result back into the JSON file for a human to spot-check.

Usage:
    OPENAI_API_KEY=... python scripts/fill_voice_library_ref_text.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from story_engine.agents.voice_provider import OpenAIVoiceProvider  # noqa: E402

_LIBRARY_PATH = Path(__file__).resolve().parents[1] / "indicf5_tts" / "voice_library.json"
_TTS_ROOT = _LIBRARY_PATH.parent


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")

    library = json.loads(_LIBRARY_PATH.read_text(encoding="utf-8"))
    provider = OpenAIVoiceProvider(api_key=api_key)

    changed = False
    for voice in library["voices"]:
        if voice.get("ref_text"):
            continue
        clip_path = _TTS_ROOT / voice["file"]
        if not clip_path.exists():
            print(f"skip {voice['id']}: {clip_path} not found")
            continue
        text = provider.transcribe_chunk(
            audio_bytes=clip_path.read_bytes(),
            model="whisper-1",
            content_type="audio/wav",
        )
        if text:
            voice["ref_text"] = text
            changed = True
            print(f"{voice['id']}: {text}")
        else:
            print(f"{voice['id']}: transcription came back empty, left as null")

    if changed:
        _LIBRARY_PATH.write_text(json.dumps(library, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Updated {_LIBRARY_PATH}")


if __name__ == "__main__":
    main()
