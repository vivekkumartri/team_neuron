"""Task 4G.3 acceptance, exercised against a fake connection (no live Lakebase
needed): reconnect after event 3 receives events 4+ exactly once, and a
terminal job emits a `generation-complete` event and stops.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from story_engine.api.sse import stream_job_events

_ROWS = [
    (1, "world", "GENERATING", "World mapped the active cast.", None),
    (2, "director", "GENERATING", "Kaelen proposed an action.", None),
    (3, "storyteller", "EVALUATING", "Composing scenes.", None),
    (4, "evaluator", "PUBLISHED", "Evaluator approved the candidate.", None),
]


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]], job_status: str) -> None:
        self._rows = rows
        self._job_status = job_status
        self._result: list[tuple[Any, ...]] = []

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        if "FROM generation_events" in query:
            after_sequence = params[1]
            self._result = [row for row in self._rows if row[0] > after_sequence]
        elif "FROM generation_jobs" in query:
            self._result = [(self._job_status,)]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._result

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._result[0] if self._result else None

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]], job_status: str) -> None:
        self._rows = rows
        self._job_status = job_status

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows, self._job_status)


def _connection_factory(rows: list[tuple[Any, ...]], job_status: str) -> Any:
    @contextmanager
    def factory() -> Any:
        yield _FakeConnection(rows, job_status)

    return factory


async def test_reconnect_after_event_three_receives_four_and_onward_exactly_once() -> None:
    factory = _connection_factory(_ROWS, job_status="SUCCEEDED")
    events = [event async for event in stream_job_events(factory, uuid4(), last_event_id=3)]

    progress_ids = [event["id"] for event in events if event["event"] == "generation-progress"]
    assert progress_ids == ["4"], (
        "reconnecting after event 3 must yield exactly event 4, not a duplicate or a gap"
    )
    assert events[-1]["event"] == "generation-complete"


async def test_terminal_job_emits_completion_and_stops() -> None:
    factory = _connection_factory(_ROWS, job_status="SUCCEEDED")
    events = [event async for event in stream_job_events(factory, uuid4(), last_event_id=0)]

    assert events[-1] == {"event": "generation-complete", "data": "{}"}
    assert len(events) == len(_ROWS) + 1
