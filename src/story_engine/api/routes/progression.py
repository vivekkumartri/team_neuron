"""Progression: the only three ways an author advances a published chapter.

`services/progression.target_branch_for_progression` decides whether the
request stays on the current branch (`CONTINUE`) or requires a new child
branch (`EDIT_TRAITS`/`REWIND`); this route does the branch-creation and
job-queuing I/O that pure function can't do itself. Queuing a job here means:
insert a `generation_jobs` row and a same-transaction `outbox` row. Once the
transaction is committed, the app starts the bound Databricks Job. A launch
failure leaves the outbox entry retryable; it is never reported as generated.
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.api.settings import load_settings
from story_engine.domain.models import ProgressionMode, ProgressionRequest
from story_engine.services.databricks_jobs import JobLaunchError, get_job_launcher
from story_engine.services.progression import ProgressionError, target_branch_for_progression
from story_engine.services.quotas import (
    QuotaCategory,
    QuotaExceededError,
    current_quota_states,
    enforce_quota,
)
from story_engine.workers.outbox import mark_published, write_outbox_entry

router = APIRouter(prefix="/api/v1/branches", tags=["progression"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class QuotaStateResponse(BaseModel):
    category: str
    used: int
    limit: int
    remaining: int
    exceeded: bool
    approaching: bool


def _quota_response(state: object) -> QuotaStateResponse:
    return QuotaStateResponse(
        category=state.category.value,  # type: ignore[attr-defined]
        used=state.used,  # type: ignore[attr-defined]
        limit=state.limit,  # type: ignore[attr-defined]
        remaining=state.remaining,  # type: ignore[attr-defined]
        exceeded=state.exceeded,  # type: ignore[attr-defined]
        approaching=state.approaching,  # type: ignore[attr-defined]
    )


class ProgressionRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: UUID | None = None
    focal_entity_id: UUID
    mode: ProgressionMode
    trait_change: str | None = None
    rewind_to_chapter_id: UUID | None = None


class ProgressionResponse(BaseModel):
    job_id: UUID
    branch_id: UUID
    status: str


@router.post(
    "/{branch_id}/progression",
    response_model=ProgressionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_progression(
    branch_id: UUID,
    payload: ProgressionRequestInput,
    user: CurrentUser,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ProgressionResponse:
    request = ProgressionRequest(
        chapter_id=payload.chapter_id,
        focal_entity_id=payload.focal_entity_id,
        mode=payload.mode,
        trait_change=payload.trait_change,
        rewind_to_chapter_id=payload.rewind_to_chapter_id,
    )
    try:
        target_branch_id = target_branch_for_progression(request, branch_id)
    except ProgressionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    # A stable key is required even when the client doesn't send one, since
    # `generation_jobs` has a NOT NULL `(requested_by_user_id, idempotency_key)`
    # uniqueness constraint that this replay check relies on.
    if payload.chapter_id is None and payload.mode is not ProgressionMode.CONTINUE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chapter 1 can only start with Continue automatically",
        )
    key = idempotency_key or f"auto-{payload.chapter_id or 'chapter-1'}-{payload.mode.value}"

    with tenant_connection(user) as connection:
        outbox_id: UUID | None = None
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, branch_id, status FROM generation_jobs "
                "WHERE requested_by_user_id = %s AND idempotency_key = %s",
                (user.id, key),
            )
            existing = cursor.fetchone()
            if existing is not None:
                values = cast(tuple[Any, ...], existing)
                return ProgressionResponse(
                    job_id=UUID(str(values[0])),
                    branch_id=UUID(str(values[1])),
                    status=str(values[2]),
                )

            if target_branch_id is None:
                # EDIT_TRAITS / REWIND: a validated child branch, never a
                # mutation of the current branch or its published chapters.
                cursor.execute(
                    "SELECT story_id, arc_id, name FROM branches WHERE id = %s", (branch_id,)
                )
                parent_row = cursor.fetchone()
                if parent_row is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found"
                    )
                story_id, arc_id, parent_name = cast(tuple[Any, ...], parent_row)
                suffix = "trait-edit" if payload.mode is ProgressionMode.EDIT_TRAITS else "rewind"
                cursor.execute(
                    "INSERT INTO branches (story_id, arc_id, parent_branch_id, name, status) "
                    "VALUES (%s, %s, %s, %s, 'ACTIVE') RETURNING id",
                    (story_id, arc_id, branch_id, f"{parent_name} ({suffix})"),
                )
                target_branch_id = cast(tuple[Any, ...], cursor.fetchone())[0]

        # Quota check happens after idempotency replay (a replayed request must
        # never be re-blocked) but before the job row is inserted, so a
        # rejected submission never creates a QUEUED job or outbox entry.
        for state in current_quota_states(connection, user_id=user.id):
            if state.category is QuotaCategory.CONCURRENT_GENERATION_JOBS:
                try:
                    enforce_quota(state)
                except QuotaExceededError as error:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={"quota": _quota_response(error.state).model_dump()},
                    ) from error

        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO generation_jobs "
                    "(branch_id, requested_by_user_id, idempotency_key, status) "
                    "VALUES (%s, %s, %s, 'QUEUED') RETURNING id, status",
                    (target_branch_id, user.id, key),
                )
            except Exception as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This branch already has an active generation job",
                ) from error
            job_row = cast(tuple[Any, ...], cursor.fetchone())
            job_id, job_status = UUID(str(job_row[0])), str(job_row[1])

            outbox_id = write_outbox_entry(
                connection,
                aggregate_type="generation_job",
                aggregate_id=job_id,
                event_type="GENERATION_REQUESTED",
                payload={"mode": payload.mode.value},
            )
        connection.commit()
        try:
            get_job_launcher(load_settings()).launch(job_key="generation_job", job_id=job_id)
        except JobLaunchError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Generation was queued but the worker could not be started. Please retry.",
            ) from error
        if outbox_id is not None:
            mark_published(connection, outbox_id)

    return ProgressionResponse(
        job_id=job_id, branch_id=UUID(str(target_branch_id)), status=job_status
    )


me_quota_router = APIRouter(prefix="/api/v1/me", tags=["quota"])


@me_quota_router.get("/quota", response_model=list[QuotaStateResponse])
def get_my_quota(user: CurrentUser) -> list[QuotaStateResponse]:
    with tenant_connection(user) as connection:
        states = current_quota_states(connection, user_id=user.id)
    return [_quota_response(state) for state in states]
