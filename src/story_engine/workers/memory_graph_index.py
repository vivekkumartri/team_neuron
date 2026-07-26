"""Databricks Job wheel-task entry point for memory-graph indexing.

Registered the same way `memory_compaction_job` is (see `resources/jobs.yml`
and `workers/memory_compaction.py`, whose `_branch_owner` and
`_characters_with_episodic_memory` helpers this module reuses rather than
duplicating). Runs as a post-publication Databricks Job, not inline on the
request path — matching how every other async operation in this codebase
works (integration plan Section 1).

Per beat this does, per character with fresh episodic memory on the branch:
  1. Build one extraction passage from their most recent episodic entries
     (`relation_extract.py`), run triple extraction, and persist it as a
     `passage_nodes` row plus new `fact_nodes` rows (Session 2).
  2. Run conflict detection (`conflict.py`) between the newly inserted facts
     and this character's existing ACTIVE facts, and apply the resulting
     supersede/contest decisions (Session 3).

Honesty note, per this repo's own `task.md` convention ("if it isn't run
against a live dev workspace in a given session, say so rather than claim
it passed"): the SQL below is hand-reviewed against the real schema in
`migrations/0004_memory_and_director.sql` and
`migrations/0023_memory_graph.sql`, but has NOT been executed against a live
Lakebase/Postgres workspace in this session — this sandbox has no `psycopg`
installed to connect with. Run `databricks bundle validate -t dev` and a
real dev-workspace job invocation before trusting this in production.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any, cast
from uuid import UUID

from psycopg import Connection

from story_engine.agents.provider import OpenAIResponsesProvider
from story_engine.api.settings import RuntimeSettings, load_settings
from story_engine.memory_graph.conflict import ConflictResolutionAction, detect_conflicts
from story_engine.memory_graph.relation_extract import extract_facts_from_passage
from story_engine.memory_graph.schema import FactNode, FactStatus
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.persistence.tenant_context import set_tenant_context
from story_engine.workers.memory_compaction import (
    _branch_owner,
    _characters_with_episodic_memory,
)

logger = logging.getLogger(__name__)

DEFAULT_PASSAGE_ENTRY_LIMIT = 10


def _load_openai_api_key(settings: RuntimeSettings) -> str:
    """Same pattern as `workers/generation_job.py::_load_openai_api_key`.

    Not imported from there directly: that helper is module-private
    (leading underscore) in a module whose own top-level `main()` this
    module must not trigger the side effects of importing.
    """

    if settings.openai_api_key:
        return settings.openai_api_key
    from databricks.sdk import WorkspaceClient

    secret = WorkspaceClient().secrets.get_secret(
        scope=settings.openai_secret_scope, key=settings.openai_secret_key
    )
    value = secret.value
    if value is None:
        raise RuntimeError("OpenAI secret is unavailable to the memory-graph index job")
    import base64

    try:
        return base64.b64decode(value).decode("utf-8")
    except (TypeError, ValueError, UnicodeDecodeError):
        raise RuntimeError("OpenAI secret is malformed") from None


def _content_to_text(content: object) -> str:
    """`character_memories.content` is JSONB; render it as extraction-ready text.

    Written EPISODIC rows in this codebase are free-form JSON (see
    `memory_compaction.py`'s own compacted-entry shape, `{"compacted": ...,
    "entries": [...]}`, alongside plain string entries written elsewhere) —
    there is no single canonical shape today, so this stays defensive rather
    than assuming one.
    """

    if isinstance(content, str):
        return content
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return cast(str, content["text"])
    return json.dumps(content)


def _recent_episodic_passage_text(
    connection: Connection[object],
    *,
    branch_id: UUID,
    character_id: UUID,
    limit: int = DEFAULT_PASSAGE_ENTRY_LIMIT,
) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT content FROM character_memories "
            "WHERE branch_id = %s AND character_id = %s AND memory_kind = 'EPISODIC' "
            "ORDER BY created_at DESC LIMIT %s",
            (branch_id, character_id, limit),
        )
        rows = cursor.fetchall()
    # DESC in the query keeps LIMIT cheap; reverse here so the passage reads
    # oldest-first, matching `relation_extract.passage_text_from_episodic_memory`.
    texts = [_content_to_text(cast(tuple[Any, ...], row)[0]) for row in reversed(rows)]
    return "\n".join(texts)


def _insert_passage(
    connection: Connection[object],
    *,
    branch_id: UUID,
    character_id: UUID,
    source_chapter_id: UUID,
    text: str,
) -> UUID:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO passage_nodes (branch_id, character_id, source_chapter_id, text) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (branch_id, character_id, source_chapter_id, text[:5_000]),
        )
        row = cursor.fetchone()
    return UUID(str(cast(tuple[Any, ...], row)[0]))


def _load_active_facts(
    connection: Connection[object], *, branch_id: UUID, character_id: UUID
) -> list[FactNode]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, head, head_type, relation, relation_type, tail, tail_type, "
            "confidence, source_chapter_id, visible_through_chapter_id "
            "FROM fact_nodes WHERE branch_id = %s AND character_id = %s AND status = 'ACTIVE'",
            (branch_id, character_id),
        )
        rows = cursor.fetchall()
    facts: list[FactNode] = []
    for row in rows:
        columns = cast(tuple[Any, ...], row)
        facts.append(
            FactNode(
                id=columns[0],
                branch_id=branch_id,
                character_id=character_id,
                head=columns[1],
                head_type=columns[2],
                relation=columns[3],
                relation_type=columns[4],
                tail=columns[5],
                tail_type=columns[6],
                confidence=columns[7],
                source_chapter_id=columns[8],
                visible_through_chapter_id=columns[9],
                status=FactStatus.ACTIVE,
            )
        )
    return facts


def _insert_facts(
    connection: Connection[object], facts: tuple[FactNode, ...], *, passage_id: UUID
) -> list[FactNode]:
    inserted: list[FactNode] = []
    with connection.cursor() as cursor:
        for fact in facts:
            cursor.execute(
                "INSERT INTO fact_nodes (branch_id, character_id, head, head_type, relation, "
                "relation_type, tail, tail_type, confidence, source_chapter_id, "
                "visible_through_chapter_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id",
                (
                    fact.branch_id,
                    fact.character_id,
                    fact.head,
                    fact.head_type,
                    fact.relation,
                    fact.relation_type,
                    fact.tail,
                    fact.tail_type,
                    fact.confidence,
                    fact.source_chapter_id,
                    fact.visible_through_chapter_id,
                ),
            )
            new_id = UUID(str(cast(tuple[Any, ...], cursor.fetchone())[0]))
            cursor.execute(
                "INSERT INTO fact_passage_links (fact_id, passage_id) VALUES (%s, %s)",
                (new_id, passage_id),
            )
            inserted.append(fact.model_copy(update={"id": new_id}))
    return inserted


def _apply_conflict_resolution(
    connection: Connection[object], *, earlier: FactNode, later: FactNode, action: str
) -> None:
    if action == ConflictResolutionAction.SUPERSEDE_EARLIER:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE fact_nodes SET status = 'SUPERSEDED', superseded_by = %s WHERE id = %s",
                (later.id, earlier.id),
            )
    elif action == ConflictResolutionAction.FLAG_FOR_REVIEW:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE fact_nodes SET status = 'CONTESTED' WHERE id = ANY(%s)",
                ([earlier.id, later.id],),
            )
    # KEEP_BOTH: no row change; the "conflict" was only a granularity match.


def index_character_memory_graph(
    connection: Connection[object],
    provider: OpenAIResponsesProvider,
    *,
    model: str,
    branch_id: UUID,
    character_id: UUID,
    source_chapter_id: UUID,
) -> int:
    """Extract + conflict-resolve one character's fact graph. Returns facts inserted."""

    passage_text = _recent_episodic_passage_text(
        connection, branch_id=branch_id, character_id=character_id
    )
    if not passage_text.strip():
        return 0

    new_facts = extract_facts_from_passage(
        provider,
        model=model,
        branch_id=branch_id,
        character_id=character_id,
        passage_text=passage_text,
        source_chapter_id=source_chapter_id,
    )
    if not new_facts:
        return 0

    passage_id = _insert_passage(
        connection,
        branch_id=branch_id,
        character_id=character_id,
        source_chapter_id=source_chapter_id,
        text=passage_text,
    )
    inserted = _insert_facts(connection, new_facts, passage_id=passage_id)

    existing = _load_active_facts(connection, branch_id=branch_id, character_id=character_id)
    all_active = existing + inserted
    conflicts = detect_conflicts(provider, model=model, facts=all_active)
    for fact_a, fact_b, result in conflicts:
        _apply_conflict_resolution(
            connection, earlier=fact_a, later=fact_b, action=result.action.value
        )

    return len(inserted)


def run_memory_graph_index(branch_id: UUID, chapter_id: UUID) -> None:
    """Index the memory graph for every character with fresh episodic memory on a branch."""

    settings = load_settings()
    api_key = _load_openai_api_key(settings)
    provider = OpenAIResponsesProvider(api_key=api_key)

    with lakebase_connection(settings) as connection:
        owner_id = _branch_owner(connection, branch_id=branch_id)
        if owner_id is None:
            logger.info("Branch %s does not exist; nothing to index", branch_id)
            return
        set_tenant_context(connection, owner_id)

        total_inserted = 0
        for character_id in _characters_with_episodic_memory(connection, branch_id=branch_id):
            total_inserted += index_character_memory_graph(
                connection,
                provider,
                model=settings.openai_model,
                branch_id=branch_id,
                character_id=character_id,
                source_chapter_id=chapter_id,
            )
        connection.commit()
        logger.info(
            "Memory-graph index for branch %s chapter %s inserted %d fact(s)",
            branch_id,
            chapter_id,
            total_inserted,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch-id", required=True, type=UUID)
    parser.add_argument("--chapter-id", required=True, type=UUID)
    args = parser.parse_args()
    run_memory_graph_index(args.branch_id, args.chapter_id)


if __name__ == "__main__":
    main()
