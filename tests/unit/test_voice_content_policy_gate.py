"""Unit coverage that a voice transcript is run through the same
content-policy gate as typed text before it can become a `final` transcript.

This exercises `api/routes/voice._emit_final` directly with a fake
WebSocket-like sink, so it needs no network, no audio codec, and no live
OpenAI/Lakebase connection — only `RuleBasedContentPolicy`, which is the
same deterministic gate `generation_pipeline.py` already uses for candidate
prose.
"""

from __future__ import annotations

import asyncio

from story_engine.api.routes.voice import _emit_final
from story_engine.security.content_policy import RuleBasedContentPolicy


class _RecordingSink:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)


def test_benign_transcript_is_emitted_as_final() -> None:
    sink = _RecordingSink()
    asyncio.run(
        _emit_final(
            sink,
            ["A lighthouse", "keeper hears distant ships."],
            RuleBasedContentPolicy(),
        )
    )

    assert len(sink.sent) == 1
    assert sink.sent[0]["type"] == "final"
    assert "lighthouse" in sink.sent[0]["text"]


def test_policy_violating_transcript_is_rejected_not_finalized() -> None:
    sink = _RecordingSink()
    asyncio.run(
        _emit_final(
            sink,
            ["Make the villain", "more violent and crueller with every scene."],
            RuleBasedContentPolicy(),
        )
    )

    assert len(sink.sent) == 1
    assert sink.sent[0]["type"] == "rejected"
    assert "safe_alternative" in sink.sent[0]


def test_empty_transcript_is_still_emitted_as_final_with_no_gate_bypass() -> None:
    sink = _RecordingSink()
    asyncio.run(_emit_final(sink, [], RuleBasedContentPolicy()))

    assert sink.sent == [{"type": "final", "text": ""}]
