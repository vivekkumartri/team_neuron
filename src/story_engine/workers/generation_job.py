"""Databricks wheel entry point for real, evaluator-gated chapter generation."""

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

from story_engine.agents.prompts.system import (
    CHARACTER,
    DIRECTOR,
    EVALUATOR,
    WORLD,
    storyteller_prompt_for_language,
)
from story_engine.agents.provider import ModelProviderError, OpenAIResponsesProvider
from story_engine.analytics.observability import CorrelatedLogRecord, MetricEvent, emit
from story_engine.api.settings import RuntimeSettings, load_settings
from story_engine.domain.models import StoryLanguage
from story_engine.domain.policy_models import PolicyDecision, PolicySubject
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.persistence.tenant_context import set_tenant_context
from story_engine.security.content_policy import RuleBasedContentPolicy
from story_engine.workers.queue import claim_job, release_job

logger = logging.getLogger(__name__)


def _load_openai_api_key(settings: RuntimeSettings) -> str:
    """Read the runtime key without printing, persisting, or returning it to a client."""

    if settings.openai_api_key:
        return settings.openai_api_key
    secret = WorkspaceClient().secrets.get_secret(
        scope=settings.openai_secret_scope, key=settings.openai_secret_key
    )
    value = secret.value
    if value is None:
        raise RuntimeError("OpenAI secret is unavailable to the generation job")
    try:
        return base64.b64decode(value).decode("utf-8")
    except (TypeError, ValueError, UnicodeDecodeError):
        raise RuntimeError("OpenAI secret is malformed") from None


def _write_event(
    connection: Connection[object],
    *,
    job_id: UUID,
    sequence: int,
    agent: str,
    recipient: str | None,
    status: str,
    summary: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO generation_events "
            "(job_id, sequence, agent_label, recipient_agent_label, status, summary) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (job_id, sequence, agent, recipient, status, summary[:500]),
        )


def _write_run(connection: Connection[object], *, job_id: UUID, agent: str, summary: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO agent_runs (job_id, agent_label, status, redacted_summary) "
            "VALUES (%s, %s, 'SUCCEEDED', %s)",
            (job_id, agent, summary[:500]),
        )


def _timed_complete(
    provider: OpenAIResponsesProvider,
    *,
    job_id: UUID,
    agent: str,
    system_prompt: str,
    user_data: str,
    model: str,
) -> str:
    """`provider.complete` wrapped with an `AGENT_LATENCY` metric.

    This is the first real caller of `analytics.observability.emit()` from
    inside the actual generation loop — previously only the job dispatcher
    called it, and this loop made no metric calls at all.
    """

    started = time.monotonic()
    result = provider.complete(system_prompt=system_prompt, user_data=user_data, model=model)
    emit(
        CorrelatedLogRecord(
            correlation_id=job_id,
            event=MetricEvent.AGENT_LATENCY,
            payload={"agent": agent, "seconds": round(time.monotonic() - started, 3)},
        )
    )
    return result


def run_generation_job(job_id: UUID) -> None:
    """Generate, evaluate, stage, and automatically publish one chapter."""

    settings = load_settings()
    api_key = _load_openai_api_key(settings)
    loop_started = time.monotonic()

    with lakebase_connection(settings) as connection:
        claimed = claim_job(connection, job_id)
        if claimed is None:
            logger.info("Job %s is not claimable", job_id)
            return
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT j.requested_by_user_id, s.title, e.id, e.name, s.language "
                    "FROM generation_jobs j "
                    "JOIN branches b ON b.id = j.branch_id "
                    "JOIN stories s ON s.id = b.story_id "
                    "LEFT JOIN entities e ON e.story_id = s.id AND e.entity_type = 'character' "
                    "WHERE j.id = %s ORDER BY e.created_at NULLS LAST LIMIT 1",
                    (job_id,),
                )
                row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Generation job context is unavailable")
            requester_id, story_title, focal_id, focal_name, story_language = cast(
                tuple[Any, ...], row
            )
            if focal_id is None:
                raise RuntimeError("A story needs at least one character before generation")
            set_tenant_context(connection, UUID(str(requester_id)))
            language = StoryLanguage(str(story_language))

            provider = OpenAIResponsesProvider(api_key=api_key)
            story_context = (
                f"Story title: {story_title}\nFocal character: {focal_name}\n"
                "Create an original, concise next chapter."
            )
            sequence = 1
            _write_event(
                connection,
                job_id=job_id,
                sequence=sequence,
                agent="character",
                recipient="director",
                status="GENERATING",
                summary="Character is sharing their immediate perspective with the Director.",
            )
            character = _timed_complete(
                provider,
                job_id=job_id,
                agent="character",
                system_prompt=CHARACTER,
                user_data=story_context,
                model=settings.openai_model,
            )
            _write_run(
                connection,
                job_id=job_id,
                agent="character",
                summary="Shared the focal character's public perspective.",
            )

            sequence += 1
            _write_event(
                connection,
                job_id=job_id,
                sequence=sequence,
                agent="director",
                recipient="world",
                status="GENERATING",
                summary="Director is briefing World on the proposed next beat.",
            )
            director = _timed_complete(
                provider,
                job_id=job_id,
                agent="director",
                system_prompt=DIRECTOR,
                user_data=f"{story_context}\nCharacter perspective:\n{character}",
                model=settings.openai_model,
            )
            _write_run(connection, job_id=job_id, agent="director", summary="Proposed next beat.")

            sequence += 1
            _write_event(
                connection,
                job_id=job_id,
                sequence=sequence,
                agent="world",
                recipient="storyteller",
                status="GENERATING",
                summary="World is validating branch continuity for the proposed beat.",
            )
            world = _timed_complete(
                provider,
                job_id=job_id,
                agent="world",
                system_prompt=WORLD,
                user_data=f"{story_context}\nDirector proposal:\n{director}",
                model=settings.openai_model,
            )
            _write_run(
                connection,
                job_id=job_id,
                agent="world",
                summary="Continuity review completed.",
            )

            sequence += 1
            _write_event(
                connection,
                job_id=job_id,
                sequence=sequence,
                agent="storyteller",
                recipient="evaluator",
                status="GENERATING",
                summary="Storyteller is drafting scenes and character dialogue.",
            )
            screenplay = _timed_complete(
                provider,
                job_id=job_id,
                agent="storyteller",
                system_prompt=storyteller_prompt_for_language(language),
                user_data=(
                    f"{story_context}\nCharacter perspective:\n{character}\n"
                    f"Director:\n{director}\nWorld:\n{world}"
                ),
                model=settings.openai_model,
            )
            policy = RuleBasedContentPolicy().assess(screenplay, PolicySubject.CANDIDATE_PROSE)
            if policy.decision is not PolicyDecision.ALLOW:
                raise RuntimeError("Candidate was blocked by content policy")
            _write_run(
                connection,
                job_id=job_id,
                agent="storyteller",
                summary="Drafted candidate chapter.",
            )

            sequence += 1
            _write_event(
                connection,
                job_id=job_id,
                sequence=sequence,
                agent="evaluator",
                recipient="director",
                status="EVALUATING",
                summary="Evaluator is checking the candidate before publication.",
            )
            evaluator = _timed_complete(
                provider,
                job_id=job_id,
                agent="evaluator",
                system_prompt=EVALUATOR,
                user_data=f"{story_context}\nWorld constraints:\n{world}\nCandidate:\n{screenplay}",
                model=settings.openai_model,
            )
            if not evaluator:
                raise RuntimeError("Evaluator returned no review")
            approved = evaluator.lstrip().upper().startswith("APPROVE")
            _write_run(
                connection,
                job_id=job_id,
                agent="evaluator",
                summary=(
                    "Evaluator approved candidate."
                    if approved
                    else "Evaluator rejected candidate and requested regeneration."
                ),
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO candidate_chapters "
                    "(job_id, branch_id, focal_character_id, screenplay, status) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (
                        job_id,
                        claimed.branch_id,
                        focal_id,
                        Jsonb({"screenplay": screenplay}),
                        "APPROVED" if approved else "REJECTED",
                    ),
                )
                candidate_id = UUID(str(cast(tuple[Any, ...], cursor.fetchone())[0]))
                cursor.execute(
                    "INSERT INTO evaluator_reports (candidate_id, outcome, redacted_summary) "
                    "VALUES (%s, %s, %s)",
                    (
                        candidate_id,
                        "APPROVED" if approved else "MAJOR_DIVERGENCE",
                        (
                            "Evaluator completed the pre-publication review."
                            if approved
                            else "Evaluator rejected the candidate; regeneration is required."
                        ),
                    ),
                )
                if approved:
                    cursor.execute(
                        "SELECT world_publish_generated_candidate(%s, %s)",
                        (job_id, candidate_id),
                    )
            sequence += 1
            _write_event(
                connection,
                job_id=job_id,
                sequence=sequence,
                agent="director",
                recipient=None,
                status="PUBLISHED" if approved else "BLOCKED",
                summary=(
                    "World committed the approved chapter to this branch."
                    if approved
                    else "Publication was blocked; the evaluator requested regeneration."
                ),
            )
            connection.commit()
            release_job(connection, job_id, status="SUCCEEDED" if approved else "BLOCKED")
            emit(
                CorrelatedLogRecord(
                    correlation_id=job_id,
                    event=MetricEvent.CHAPTER_LOOP_COMPLETION,
                    payload={
                        "outcome": "SUCCEEDED" if approved else "BLOCKED",
                        "seconds": round(time.monotonic() - loop_started, 3),
                    },
                )
            )
        except (ModelProviderError, RuntimeError, ValueError):
            logger.exception("Generation job %s failed", job_id)
            connection.rollback()
            release_job(connection, job_id, status="FAILED")
            emit(
                CorrelatedLogRecord(
                    correlation_id=job_id,
                    event=MetricEvent.CHAPTER_LOOP_COMPLETION,
                    payload={
                        "outcome": "FAILED",
                        "seconds": round(time.monotonic() - loop_started, 3),
                    },
                )
            )
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True, type=UUID)
    args = parser.parse_args()
    run_generation_job(args.job_id)


if __name__ == "__main__":
    main()
