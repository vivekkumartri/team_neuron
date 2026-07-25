"""Transactional job leasing over the durable Lakebase queue.

`generation_jobs` already enforces one active job per branch via
`generation_jobs_one_active_branch_idx` (migration 0005). This module adds the
lease/claim semantics needed for safe worker crash-recovery: a claimed job
records `lease_expires_at`; a second worker may reclaim an expired lease.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from psycopg import Connection

DEFAULT_LEASE_SECONDS = 300


@dataclass(frozen=True)
class ClaimedJob:
    id: UUID
    branch_id: UUID
    attempt: int


def claim_next_job(
    connection: Connection[object], *, lease_seconds: int = DEFAULT_LEASE_SECONDS
) -> ClaimedJob | None:
    """Atomically claim one queued (or lease-expired running) job.

    Uses `SELECT ... FOR UPDATE SKIP LOCKED` so concurrent workers never
    claim the same row, and bumps `retry_count` only when reclaiming an
    expired lease (i.e. a previous worker crashed mid-job) rather than on
    every claim.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, branch_id, retry_count, lease_expires_at FROM generation_jobs "
            "WHERE status = 'QUEUED' "
            "   OR (status = 'RUNNING' AND lease_expires_at < now()) "
            "ORDER BY created_at "
            "FOR UPDATE SKIP LOCKED "
            "LIMIT 1"
        )
        fetched_row = cursor.fetchone()
        if fetched_row is None:
            return None
        job_id, branch_id, retry_count, lease_expires_at = cast(tuple[Any, ...], fetched_row)

        is_reclaim = lease_expires_at is not None
        next_attempt = retry_count + 1 if is_reclaim else retry_count

        cursor.execute(
            "UPDATE generation_jobs SET status = 'RUNNING', retry_count = %s, "
            "lease_expires_at = now() + %s, updated_at = now() WHERE id = %s",
            (next_attempt, timedelta(seconds=lease_seconds), job_id),
        )
    connection.commit()
    return ClaimedJob(id=job_id, branch_id=branch_id, attempt=next_attempt)


def claim_job(connection: Connection[object], job_id: UUID) -> ClaimedJob | None:
    """Claim one specified queued job without taking another job from the queue."""

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, branch_id, retry_count FROM generation_jobs "
            "WHERE id = %s AND status = 'QUEUED' FOR UPDATE SKIP LOCKED",
            (job_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        values = cast(tuple[Any, ...], row)
        cursor.execute(
            "UPDATE generation_jobs SET status = 'RUNNING', lease_expires_at = now() + %s, "
            "updated_at = now() WHERE id = %s",
            (timedelta(seconds=DEFAULT_LEASE_SECONDS), job_id),
        )
    connection.commit()
    return ClaimedJob(
        id=UUID(str(values[0])), branch_id=UUID(str(values[1])), attempt=int(values[2])
    )


def release_job(connection: Connection[object], job_id: UUID, *, status: str) -> None:
    """Release a job's lease and set its terminal (or requeued) status."""

    if status not in {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "QUEUED"}:
        raise ValueError(f"Unsupported release status: {status!r}")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE generation_jobs SET status = %s, lease_expires_at = NULL, "
            "updated_at = now() WHERE id = %s",
            (status, job_id),
        )
    connection.commit()
