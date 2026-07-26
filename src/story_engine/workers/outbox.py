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
from psycopg.types.json import Jsonb

# NOTE: this writes through the `world_write_outbox_entry` SECURITY DEFINER
# function (migration 0018), not a raw INSERT. The prior raw-INSERT +
# client-role RLS-policy approach (`outbox_insert_by_job_owner`) kept
# rejecting the live request-time write with `InsufficientPrivilege: new
# row violates row-level security policy for table "outbox"` even though
# the owning `generation_jobs` row was inserted moments earlier in the same
# transaction -- see migration 0018's comment for the full story. Routing
# through the function sidesteps whatever made that RLS check fail live,
# the same way `world_commit_entity_state`/`world_publish_generated_candidate`
# already do for their tables.


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
            "SELECT world_write_outbox_entry(%s, %s, %s, %s)",
            (aggregate_type, str(aggregate_id), event_type, Jsonb(payload)),
        )
        row = cursor.fetchone()
    assert row is not None
    return UUID(str(cast(tuple[Any, ...], row)[0]))
