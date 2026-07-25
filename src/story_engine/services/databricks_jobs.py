"""Databricks Jobs launcher used by the API after a request is durably queued."""

from __future__ import annotations

import os
from uuid import UUID

from databricks.sdk import WorkspaceClient


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
