"""Unit coverage for the new voice/TTS settings fields (pure, no network/DB)."""

from __future__ import annotations

from story_engine.api.settings import load_settings


def test_voice_settings_have_safe_defaults(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_TRANSCRIPTION_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TTS_MODEL", raising=False)
    monkeypatch.delenv("NARRATOR_VOICE", raising=False)

    settings = load_settings()

    assert settings.openai_transcription_model == "whisper-1"
    assert settings.openai_tts_model == "tts-1"
    assert settings.narrator_voice == "alloy"


def test_voice_settings_are_overridable_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-2")
    monkeypatch.setenv("OPENAI_TTS_MODEL", "tts-2-hd")
    monkeypatch.setenv("NARRATOR_VOICE", "onyx")

    settings = load_settings()

    assert settings.openai_transcription_model == "whisper-2"
    assert settings.openai_tts_model == "tts-2-hd"
    assert settings.narrator_voice == "onyx"
