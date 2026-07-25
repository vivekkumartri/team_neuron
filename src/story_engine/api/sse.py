"""Ordered, redacted, reconnectable generation-event SSE source.

Reads only allowlisted `generation_events` columns from Lakebase — never a
raw agent payload — and supports resuming from `Last-Event-ID` so a
reconnect after N events receives events N+1 onward exactly once.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from psycopg import Connection

from story_engine.domain.events import ClientGenerationEvent, PublicAgentLabel
from story_engine.domain.models import ChapterStatus

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.0
HEARTBEAT_EVERY_N_POLLS = 15
MAX_POLLS = 300  # bounded polling: ~5 minutes at the default interval


def _row_to_event(row: tuple[Any, ...]) -> ClientGenerationEvent | None:
    # Five-column rows are retained only for pre-migration unit fixtures;
    # deployed databases return the six-column coordination-aware shape.
    if len(row) == 5:
        sequence, agent_label, status, summary, public_entity_id = row
        recipient_agent_label = None
    else:
        sequence, agent_label, recipient_agent_label, status, summary, public_entity_id = row
    try:
        agent = PublicAgentLabel(agent_label)
        recipient_agent = (
            PublicAgentLabel(recipient_agent_label) if recipient_agent_label is not None else None
        )
        chapter_status = ChapterStatus(status)
    except ValueError:
        # A malformed/legacy row must never break the stream or leak an
        # unrecognized value to the client; skip it and let the sequence
        # gap be visible in the reconnect cursor instead.
        logger.warning("Skipping generation_event with unrecognized agent/status: %r", row)
        return None
    return ClientGenerationEvent(
        sequence=sequence,
        summary=summary,
        agent=agent,
        recipient_agent=recipient_agent,
        status=chapter_status,
        entity_id=UUID(str(public_entity_id)) if public_entity_id is not None else None,
    )


def fetch_events_after(
    connection: Connection[object], job_id: UUID, *, after_sequence: int
) -> list[ClientGenerationEvent]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT sequence, agent_label, recipient_agent_label, status, summary, "
            "public_entity_id "
            "FROM generation_events WHERE job_id = %s AND sequence > %s ORDER BY sequence",
            (job_id, after_sequence),
        )
        rows = cast(list[tuple[Any, ...]], cursor.fetchall())
    events = [_row_to_event(row) for row in rows]
    return [event for event in events if event is not None]


def job_is_terminal(connection: Connection[object], job_id: UUID) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT status FROM generation_jobs WHERE id = %s", (job_id,))
        row = cursor.fetchone()
    if row is None:
        return True
    status = cast(tuple[Any, ...], row)[0]
    return cast(str, status) in {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"}


async def stream_job_events(
    connection_factory: Any,
    job_id: UUID,
    *,
    last_event_id: int = 0,
) -> AsyncIterator[dict[str, str]]:
    """Yield SSE-shaped dicts for `sse_starlette.EventSourceResponse`.

    `connection_factory` is a zero-arg callable returning a fresh, tenant-scoped
    connection (RLS already re-authorizes every poll, so a revoked/expired
    session stops receiving events on its very next poll, not just at
    initial connect).
    """

    cursor_sequence = last_event_id
    polls_since_heartbeat = 0
    for _ in range(MAX_POLLS):
        with connection_factory() as connection:
            events = fetch_events_after(connection, job_id, after_sequence=cursor_sequence)
            terminal = job_is_terminal(connection, job_id)

        if events:
            polls_since_heartbeat = 0
            for event in events:
                cursor_sequence = event.sequence
                yield {
                    "event": "generation-progress",
                    "id": str(event.sequence),
                    "data": event.model_dump_json(),
                }
        else:
            polls_since_heartbeat += 1

        if terminal:
            yield {"event": "generation-complete", "data": "{}"}
            return

        if not events and polls_since_heartbeat >= HEARTBEAT_EVERY_N_POLLS:
            polls_since_heartbeat = 0
            yield {"event": "heartbeat", "data": "{}"}

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
