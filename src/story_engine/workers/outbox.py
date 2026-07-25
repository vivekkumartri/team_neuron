"""Outbox delivery: the database write and the async enqueue never diverge.

`outbox` (migration 0005) is the append-only record; a row is only marked
`published_at` once the corresponding Databricks Job has actually been
launched. A failed launch leaves the row unpublished and therefore retryable
on the next poll — it never silently disappears and never gets redelivered
as a duplicate chapter/event (see `job_dispatcher.dispatch_pending`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from psycopg import Connection


@dataclass(frozen=True)
class OutboxEntry:
    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: dict[str, object]


def fetch_unpublished(connection: Connection[object], *, limit: int = 25) -> list[OutboxEntry]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, aggregate_type, aggregate_id, event_type, payload FROM outbox "
            "WHERE published_at IS NULL ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED",
            (limit,),
        )
        rows = cast(list[tuple[Any, ...]], cursor.fetchall())
    return [
        OutboxEntry(
            id=row[0], aggregate_type=row[1], aggregate_id=row[2], event_type=row[3], payload=row[4]
        )
        for row in rows
    ]


def mark_published(connection: Connection[object], entry_id: UUID) -> None:
    with connection.cursor() as cursor:
        cursor.execute("UPDATE outbox SET published_at = now() WHERE id = %s", (entry_id,))
    connection.commit()


def write_outbox_entry(
    connection: Connection[object],
    *,
    aggregate_type: str,
    aggregate_id: UUID,
    event_type: str,
    payload: dict[str, object],
) -> UUID:
    """Write the outbox row in the *same transaction* as the aggregate write.

    Callers must not commit between the aggregate insert/update and this
    call — that's what makes the write and the enqueue atomic.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (aggregate_type, str(aggregate_id), event_type, payload),
        )
        row = cursor.fetchone()
    assert row is not None
    return UUID(str(cast(tuple[Any, ...], row)[0]))
