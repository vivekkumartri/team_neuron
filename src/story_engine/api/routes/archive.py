"""Archive/unarchive a chapter, and retry a blocked/failed generation job.

Archiving is a soft, reversible state flag (`chapters.archived_at`) written
through the `world_set_chapter_archived` SECURITY DEFINER function — never a
delete, and never a plain `UPDATE` (migration 0008 revoked direct chapter
DML). Retrying a job creates a *new* `generation_jobs` row rather than
resetting the failed one in place, following the same outbox pattern
`progression.py` uses, so a retried job is a fresh, auditable attempt rather
than a mutated history of the failed one.
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.workers.outbox import write_outbox_entry

router = APIRouter(prefix="/api/v1", tags=["recovery"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]

_RETRYABLE_STATUSES = ("BLOCKED", "FAILED")


class ChapterArchiveResponse(BaseModel):
    chapter_id: UUID
    archived: bool


def _set_archived(
    chapter_id: UUID, archived: bool, user: AuthenticatedUser
) -> ChapterArchiveResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    "SELECT world_set_chapter_archived(%s, %s)", (chapter_id, archived)
                )
                cursor.fetchone()
            except Exception as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
                ) from error
        connection.commit()
    return ChapterArchiveResponse(chapter_id=chapter_id, archived=archived)


@router.patch("/chapters/{chapter_id}/archive", response_model=ChapterArchiveResponse)
def archive_chapter(chapter_id: UUID, user: CurrentUser) -> ChapterArchiveResponse:
    return _set_archived(chapter_id, True, user)


@router.patch("/chapters/{chapter_id}/unarchive", response_model=ChapterArchiveResponse)
def unarchive_chapter(chapter_id: UUID, user: CurrentUser) -> ChapterArchiveResponse:
    return _set_archived(chapter_id, False, user)


class RetryResponse(BaseModel):
    job_id: UUID
    branch_id: UUID
    status: str


@router.post(
    "/generation-jobs/{job_id}/retry",
    response_model=RetryResponse,
    status_code=status.HTTP_201_CREATED,
)
def retry_generation_job(job_id: UUID, user: CurrentUser) -> RetryResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT branch_id, status FROM generation_jobs "
                "WHERE id = %s AND requested_by_user_id = %s",
                (job_id, user.id),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
            branch_id, current_status = cast(tuple[Any, ...], row)
            if str(current_status) not in _RETRYABLE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Only {_RETRYABLE_STATUSES} jobs can be retried, this job is "
                    f"{current_status}",
                )

            cursor.execute(
                "INSERT INTO generation_jobs "
                "(branch_id, requested_by_user_id, idempotency_key, status) "
                "VALUES (%s, %s, %s, 'QUEUED') RETURNING id, status",
                (branch_id, user.id, f"retry-{job_id}"),
            )
            new_row = cast(tuple[Any, ...], cursor.fetchone())
            new_job_id, new_status = UUID(str(new_row[0])), str(new_row[1])

            write_outbox_entry(
                connection,
                aggregate_type="generation_job",
                aggregate_id=new_job_id,
                event_type="GENERATION_REQUESTED",
                payload={"retry_of": str(job_id)},
            )
        connection.commit()

    return RetryResponse(job_id=new_job_id, branch_id=UUID(str(branch_id)), status=new_status)
