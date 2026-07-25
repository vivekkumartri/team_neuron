"""Databricks Job wheel-task entry point for post-publication evaluator/business reports.

Runs after a chapter is published; a failure here must never unpublish a
valid chapter (design.md: "Business failure creates pending/failed report
but chapter remains readable/published when evaluator passed").
"""

from __future__ import annotations

import argparse
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


def run_report_job(chapter_id: UUID) -> None:
    """Run the evaluator and business report generation for one chapter.

    Extension point: wire `agents.evaluator` / `agents.business` adapters
    here once real model calls exist. Intentionally not stubbed to a fake
    success — see `generation_job.run_generation_job` for the same reasoning.
    """

    raise NotImplementedError(
        f"Wire agents.evaluator/agents.business report generation for chapter {chapter_id} "
        "here once real model adapters exist."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter-id", required=True, type=UUID)
    args = parser.parse_args()
    run_report_job(args.chapter_id)


if __name__ == "__main__":
    main()
