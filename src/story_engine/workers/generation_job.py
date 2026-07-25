"""Databricks Job wheel-task entry point for chapter generation.

Invoked as `python -m story_engine.workers.generation_job --job-id <uuid>`.
Receives only a tenant-safe job identifier; all other context (branch,
tenant, memory, world snapshot) is loaded from Lakebase using that ID, never
passed as a job parameter (Task 3F.1).
"""

from __future__ import annotations

import argparse
import logging
from uuid import UUID

from story_engine.api.settings import load_settings
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.workers.queue import claim_next_job, release_job

logger = logging.getLogger(__name__)


def run_generation_job(job_id: UUID) -> None:
    """Run one generation job to completion.

    The actual Director/world discussion loop, candidate staging, and
    evaluator gate are implemented in `services.generation_pipeline` /
    `services.candidate_service`; this entry point only owns job
    lifecycle (claim -> run -> release) so it can be exercised by a real
    Databricks Job task without duplicating orchestration logic here.
    """

    settings = load_settings()
    with lakebase_connection(settings) as connection:
        claimed = claim_next_job(connection)
        if claimed is None or claimed.id != job_id:
            logger.info("Job %s is not claimable (already running or completed)", job_id)
            return
        try:
            # Orchestration hook: Track E's generate_evaluated_candidate(...)
            # plus the world-commit path runs here once wired to real model
            # adapters. Left as an explicit extension point rather than a
            # placeholder implementation, since a fabricated "success" here
            # would misrepresent an untested code path as complete.
            raise NotImplementedError(
                "Wire services.generation_pipeline.generate_evaluated_candidate "
                "and the world_commit_* functions here once real model "
                "adapters exist (see Task 3E.2's provider abstraction)."
            )
        except Exception:
            logger.exception("Generation job %s failed", job_id)
            release_job(connection, claimed.id, status="FAILED")
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True, type=UUID)
    args = parser.parse_args()
    run_generation_job(args.job_id)


if __name__ == "__main__":
    main()
