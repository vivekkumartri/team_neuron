"""Databricks Job wheel-task entry point for character memory compaction.

Task 3F.1's status note said a memory-compaction wheel task was never defined
in `resources/jobs.yml` because no entry-point function existed for it. This
module is that function.

Schema note: the task that requested this named `character_core_memory` /
`character_episodic_memory` as if they were two separate tables. Migration
`0004_memory_and_director.sql` actually created one table, `character_memories`,
with a `memory_kind` column (`'CORE' | 'EPISODIC' | 'SCREENPLAY'`) — there are
no separately named core/episodic tables to compact. This worker operates on
that real table, filtering by `memory_kind = 'EPISODIC'` (the kind that grows
unbounded turn over turn; `CORE` is small/stable trait state and isn't a
compaction target).

Compaction here is a pure DB operation (collapse old EPISODIC rows for one
character into a single summarizing row once a per-character count threshold
is exceeded) — no model call is needed or made, so this can run and be
verified in a real Postgres without an OpenAI dependency.
"""

from __future__ import annotations

import argparse
import logging
from typing import Any, cast
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from story_engine.api.settings import load_settings
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.persistence.tenant_context import set_tenant_context

logger = logging.getLogger(__name__)

DEFAULT_KEEP_RECENT = 20


def _branch_owner(connection: Connection[object], *, branch_id: UUID) -> UUID | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT s.user_id FROM branches b JOIN stories s ON s.id = b.story_id "
            "WHERE b.id = %s",
            (branch_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return UUID(str(cast(tuple[Any, ...], row)[0]))


def _characters_with_episodic_memory(
    connection: Connection[object], *, branch_id: UUID
) -> list[UUID]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT character_id FROM character_memories "
            "WHERE branch_id = %s AND memory_kind = 'EPISODIC'",
            (branch_id,),
        )
        rows = cursor.fetchall()
    return [UUID(str(cast(tuple[Any, ...], row)[0])) for row in rows]


def compact_character_episodic_memory(
    connection: Connection[object],
    *,
    branch_id: UUID,
    character_id: UUID,
    keep_recent: int = DEFAULT_KEEP_RECENT,
) -> int:
    """Collapse a character's oldest EPISODIC rows on this branch into one row.

    Keeps the `keep_recent` most-recently-created EPISODIC rows untouched;
    everything older is merged into a single new EPISODIC row and deleted.
    Returns the number of rows compacted (0 if nothing was over the threshold).
    """

    if keep_recent < 1:
        raise ValueError("keep_recent must be at least one")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, content, source_chapter_id, visible_through_chapter_id "
            "FROM character_memories "
            "WHERE branch_id = %s AND character_id = %s AND memory_kind = 'EPISODIC' "
            "ORDER BY created_at DESC",
            (branch_id, character_id),
        )
        rows = cursor.fetchall()

    if len(rows) <= keep_recent:
        return 0

    overflow = [cast(tuple[Any, ...], row) for row in rows[keep_recent:]]
    overflow_ids = [row[0] for row in overflow]
    # `visible_through_chapter_id` must never regress what a later reader sees;
    # `overflow[0]` is the most recent of the rows being removed, so its
    # visibility cutoff is the widest one the compacted row can safely carry.
    newest_overflow = overflow[0]
    oldest_overflow = overflow[-1]
    compacted_content = {
        "compacted": True,
        "compacted_count": len(overflow),
        "entries": [row[1] for row in overflow],
    }

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO character_memories "
            "(branch_id, character_id, memory_kind, content, source_chapter_id, "
            "visible_through_chapter_id) "
            "VALUES (%s, %s, 'EPISODIC', %s, %s, %s)",
            (
                branch_id,
                character_id,
                Jsonb(compacted_content),
                oldest_overflow[2],
                newest_overflow[3],
            ),
        )
        cursor.execute(
            "DELETE FROM character_memories WHERE id = ANY(%s)",
            (overflow_ids,),
        )
    return len(overflow)


def run_memory_compaction(branch_id: UUID, *, keep_recent: int = DEFAULT_KEEP_RECENT) -> None:
    """Compact episodic memory for every character on one branch."""

    settings = load_settings()
    with lakebase_connection(settings) as connection:
        owner_id = _branch_owner(connection, branch_id=branch_id)
        if owner_id is None:
            logger.info("Branch %s does not exist; nothing to compact", branch_id)
            return
        set_tenant_context(connection, owner_id)

        total_compacted = 0
        for character_id in _characters_with_episodic_memory(connection, branch_id=branch_id):
            total_compacted += compact_character_episodic_memory(
                connection,
                branch_id=branch_id,
                character_id=character_id,
                keep_recent=keep_recent,
            )
        connection.commit()
        logger.info(
            "Memory compaction for branch %s compacted %d row(s)", branch_id, total_compacted
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch-id", required=True, type=UUID)
    args = parser.parse_args()
    run_memory_compaction(args.branch_id)


if __name__ == "__main__":
    main()
