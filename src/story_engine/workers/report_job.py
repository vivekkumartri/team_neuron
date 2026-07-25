"""Databricks Job wheel-task entry point for post-publication business reports.

Runs after a chapter is published; a failure here must never unpublish a
valid chapter (design.md: "Business failure creates pending/failed report
but chapter remains readable/published when evaluator passed").

Scope note: the pre-publication evaluator review already happens inside
`generation_job.run_generation_job` (it writes the one-per-candidate
`evaluator_reports` row — that table has a `UNIQUE (candidate_id)` constraint,
so a second evaluator pass from this job would violate it, not add value).
What was actually missing end-to-end was the *business* report, so this job
calls `agents.business.BusinessAgent` only. `agents.evaluator.EvaluatorAgent`
is intentionally not re-invoked here for the reason above.

Honest gap: `business_reports` (migration 0005) has no status column, so the
"pending/failed report" state design.md describes isn't representable in the
schema today — this job's failure handling is limited to "no row exists yet"
(implicit pending) vs. a written row (succeeded); it cannot durably record a
distinct FAILED business-report state without a schema change out of this
task's scope. `budget_limit_usd` also still has no per-user config source
(same gap `generation_job.py` has), so `enforce_budget` is still not called
here — that would need a fabricated limit, which this job avoids.
"""

from __future__ import annotations

import argparse
import base64
import logging
import time
from typing import Any, cast
from uuid import UUID

from databricks.sdk import WorkspaceClient
from psycopg import Connection
from psycopg.types.json import Jsonb

from story_engine.agents.business import BusinessAgent
from story_engine.agents.provider import ModelProviderError, OpenAIResponsesProvider
from story_engine.analytics.observability import CorrelatedLogRecord, MetricEvent, emit
from story_engine.api.settings import RuntimeSettings, load_settings
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.persistence.tenant_context import set_tenant_context

logger = logging.getLogger(__name__)


def _load_openai_api_key(settings: RuntimeSettings) -> str:
    """Mirrors `generation_job._load_openai_api_key` — same secret, same rules."""

    if settings.openai_api_key:
        return settings.openai_api_key
    secret = WorkspaceClient().secrets.get_secret(
        scope=settings.openai_secret_scope, key=settings.openai_secret_key
    )
    value = secret.value
    if value is None:
        raise RuntimeError("OpenAI secret is unavailable to the report job")
    try:
        return base64.b64decode(value).decode("utf-8")
    except (TypeError, ValueError, UnicodeDecodeError):
        raise RuntimeError("OpenAI secret is malformed") from None


def _load_context(
    connection: Connection[object], *, chapter_id: UUID
) -> tuple[UUID, UUID, UUID, str, str] | None:
    """Resolve a published chapter back to its candidate/job/requester/screenplay.

    Returns `(candidate_id, job_id, requester_id, story_title, screenplay_text)`
    or `None` if the chapter has no recorded candidate link (e.g. it predates
    migration 0015, or was never produced by the generation loop).
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ch.candidate_id, cc.job_id, j.requested_by_user_id, s.title, "
            "cc.screenplay ->> 'screenplay' "
            "FROM chapters ch "
            "JOIN candidate_chapters cc ON cc.id = ch.candidate_id "
            "JOIN generation_jobs j ON j.id = cc.job_id "
            "JOIN branches b ON b.id = ch.branch_id "
            "JOIN stories s ON s.id = b.story_id "
            "WHERE ch.id = %s AND ch.candidate_id IS NOT NULL",
            (chapter_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    values = cast(tuple[Any, ...], row)
    return (
        UUID(str(values[0])),
        UUID(str(values[1])),
        UUID(str(values[2])),
        str(values[3]),
        str(values[4] or ""),
    )


def run_report_job(chapter_id: UUID) -> None:
    """Generate and persist the post-publication business report for one chapter."""

    settings = load_settings()
    api_key = _load_openai_api_key(settings)
    started = time.monotonic()

    with lakebase_connection(settings) as connection:
        context = _load_context(connection, chapter_id=chapter_id)
        if context is None:
            logger.info(
                "Chapter %s has no linked candidate; nothing for the report job to do",
                chapter_id,
            )
            return
        candidate_id, job_id, requester_id, story_title, screenplay_text = context
        set_tenant_context(connection, requester_id)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM business_reports WHERE candidate_id = %s", (candidate_id,)
            )
            if cursor.fetchone() is not None:
                logger.info("Chapter %s already has a business report", chapter_id)
                return

        try:
            provider = OpenAIResponsesProvider(api_key=api_key)
            agent = BusinessAgent(provider, model=settings.openai_model)
            proposal = agent.propose(
                chapter_id=chapter_id,
                input_text=(
                    f"Story: {story_title}\nPublished chapter screenplay:\n{screenplay_text}"
                ),
            )
            emit(
                CorrelatedLogRecord(
                    correlation_id=job_id,
                    event=MetricEvent.AGENT_LATENCY,
                    payload={"agent": "business", "seconds": round(time.monotonic() - started, 3)},
                )
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO business_reports "
                    "(candidate_id, disclosed_weighting, redacted_summary) "
                    "VALUES (%s, %s, %s) ON CONFLICT (candidate_id) DO NOTHING",
                    (candidate_id, Jsonb({}), proposal.rationale[:500]),
                )
            connection.commit()
        except (ModelProviderError, RuntimeError, ValueError):
            # Never unpublish or otherwise touch the chapter on a business-report
            # failure — the chapter stays PUBLISHED regardless. No row is written,
            # which (given the schema gap noted at module top) is the closest
            # available representation of "pending/failed".
            logger.exception("Business report generation failed for chapter %s", chapter_id)
            connection.rollback()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter-id", required=True, type=UUID)
    args = parser.parse_args()
    run_report_job(args.chapter_id)


if __name__ == "__main__":
    main()
