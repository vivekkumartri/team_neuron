"""Job launcher used by the API after a request is durably queued.

Two implementations of the same `launch(job_key, job_id)` shape: the real
Databricks Jobs launcher used in the deployed App, and a local-only
in-process launcher used when running against docker-compose Postgres
(there is no Databricks Jobs API to call locally). `get_job_launcher()` is
the single switch point so callers (`api/routes/progression.py`) never
branch on environment themselves.
"""

from __future__ import annotations

import logging
import os
import threading
from uuid import UUID

from databricks.sdk import WorkspaceClient

from story_engine.api.settings import RuntimeSettings

logger = logging.getLogger(__name__)


class JobLaunchError(RuntimeError):
    """The deployed generation Job could not be started."""


class DatabricksJobLauncher:
    """Launch a Jobs resource with its safe, single UUID parameter only."""

    def launch(self, *, job_key: str, job_id: UUID) -> None:
        if job_key != "generation_job":
            raise JobLaunchError(f"Unsupported app-launched job: {job_key}")
        configured_id = os.getenv("STORY_ENGINE_GENERATION_JOB_ID")
        if not configured_id or not configured_id.isdecimal():
            raise JobLaunchError("Generation job resource is not configured for this app")
        try:
            WorkspaceClient().jobs.run_now(
                job_id=int(configured_id), job_parameters={"job_id": str(job_id)}
            )
        except Exception as error:
            raise JobLaunchError("Generation job launch was not accepted") from error


class LocalJobLauncher:
    """Run the same wheel entry points in-process instead of a Databricks Job.

    Only ever selected by `get_job_launcher()` when `settings.local_dev_mode`
    is true (see `api/settings.py`) — never reachable in the deployed App.
    Runs in a background thread so the HTTP request that queued the job
    still returns immediately, matching the deployed App's async-launch
    behavior; a failure here is only logged (mirroring `dispatch_pending`'s
    "leave it retryable" posture) since there is no separate retry poller
    running locally.
    """

    def launch(self, *, job_key: str, job_id: UUID) -> None:
        if job_key != "generation_job":
            raise JobLaunchError(f"Unsupported local-launched job: {job_key}")

        def _run() -> None:
            # Local import: avoids a hard import-time dependency from this
            # lightweight launcher module onto the full generation worker
            # (OpenAI client, prompt templates, etc.) for callers that only
            # ever construct `DatabricksJobLauncher`.
            from story_engine.workers.generation_job import run_generation_job

            try:
                run_generation_job(job_id)
            except Exception:
                logger.exception("Local generation job %s failed", job_id)

        threading.Thread(target=_run, name=f"generation-job-{job_id}", daemon=True).start()


def get_job_launcher(settings: RuntimeSettings) -> DatabricksJobLauncher | LocalJobLauncher:
    if settings.local_dev_mode:
        return LocalJobLauncher()
    return DatabricksJobLauncher()
