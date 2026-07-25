"""The one service that turns a committed outbox row into a running Databricks Job.

Reads committed outbox rows and invokes the configured Databricks Job with
only `job_id` — never a full payload — matching Task 3F.2's requirement that
job parameters are tenant-safe identifiers, not raw data.
"""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID

from psycopg import Connection

from story_engine.workers.outbox import fetch_unpublished, mark_published

logger = logging.getLogger(__name__)


class JobLauncher(Protocol):
    """Abstraction over `WorkspaceClient().jobs.run_now(job_id=..., job_parameters=...)`.

    `job_key` is a logical key (see `_EVENT_TYPE_TO_JOB_KEY`), not a literal
    deployed job name — a real launcher implementation resolves the actual
    per-environment numeric job ID from an env var (e.g.
    `STORY_ENGINE_GENERATION_JOB_ID`), since the bundle deploys jobs named
    `story-engine-generation-${bundle.target}` (see resources/jobs.yml), and
    that target-suffixed name is an environment concern, not a dispatcher one.
    """

    def launch(self, *, job_key: str, job_id: UUID) -> None: ...


_EVENT_TYPE_TO_JOB_KEY = {
    "GENERATION_REQUESTED": "generation_job",
    "REPORT_REQUESTED": "report_job",
}


def dispatch_pending(
    connection: Connection[object], launcher: JobLauncher, *, limit: int = 25
) -> int:
    """Launch every unpublished outbox entry's Databricks Job exactly once.

    A launch failure (the launcher raising) leaves that entry unpublished so
    it is retried on the next poll rather than being dropped or, worse,
    silently re-creating a Lakebase job row.
    """

    dispatched = 0
    for entry in fetch_unpublished(connection, limit=limit):
        job_key = _EVENT_TYPE_TO_JOB_KEY.get(entry.event_type)
        if job_key is None:
            logger.warning("No job mapping for outbox event type %s", entry.event_type)
            continue
        try:
            launcher.launch(job_key=job_key, job_id=entry.aggregate_id)
        except Exception:
            logger.exception(
                "Failed to launch %s for outbox entry %s; leaving retryable", job_key, entry.id
            )
            continue
        mark_published(connection, entry.id)
        dispatched += 1
    return dispatched
