"""Author-redacted agent-run trace access, gated by `stories.agent_trace_enabled`."""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection

router = APIRouter(prefix="/api/v1", tags=["traces"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class AgentRunResponse(BaseModel):
    id: UUID
    agent_label: str
    status: str
    redacted_summary: str


class StorySettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_trace_enabled: bool


@router.get("/generation-jobs/{job_id}/agent-runs", response_model=list[AgentRunResponse])
def list_agent_runs(job_id: UUID, user: CurrentUser) -> list[AgentRunResponse]:
    """List a job's runs, still gated by the owning story's `agent_trace_enabled`.

    Closes the gap `TraceDrawer` (web/components/features/reports/TraceDrawer.tsx)
    flagged: without this, a client needed to already know a `run_id` — there
    was no way to discover one.
    """

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ar.id, ar.agent_label, ar.status, ar.redacted_summary "
                "FROM agent_runs ar "
                "JOIN generation_jobs j ON j.id = ar.job_id "
                "JOIN branches b ON b.id = j.branch_id "
                "JOIN stories s ON s.id = b.story_id "
                "WHERE j.id = %s AND s.agent_trace_enabled "
                "ORDER BY ar.created_at",
                (job_id,),
            )
            rows = cast(list[tuple[Any, ...]], cursor.fetchall())
    return [
        AgentRunResponse(
            id=UUID(str(row[0])),
            agent_label=str(row[1]),
            status=str(row[2]),
            redacted_summary=str(row[3]),
        )
        for row in rows
    ]


@router.get("/agent-runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(run_id: UUID, user: CurrentUser) -> AgentRunResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            # RLS scopes agent_runs to the caller's own generation_jobs. The
            # trace flag is checked per the job's story, not globally, so a
            # story with trace disabled never returns run detail even to its
            # own owner.
            cursor.execute(
                "SELECT ar.id, ar.agent_label, ar.status, ar.redacted_summary "
                "FROM agent_runs ar "
                "JOIN generation_jobs j ON j.id = ar.job_id "
                "JOIN branches b ON b.id = j.branch_id "
                "JOIN stories s ON s.id = b.story_id "
                "WHERE ar.id = %s AND s.agent_trace_enabled",
                (run_id,),
            )
            row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not available")
    values = cast(tuple[Any, ...], row)
    return AgentRunResponse(
        id=UUID(str(values[0])),
        agent_label=str(values[1]),
        status=str(values[2]),
        redacted_summary=str(values[3]),
    )


@router.patch(
    "/stories/{story_id}/settings",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def update_story_settings(story_id: UUID, payload: StorySettingsInput, user: CurrentUser) -> None:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE stories SET agent_trace_enabled = %s WHERE id = %s AND deleted_at IS NULL",
                (payload.agent_trace_enabled, story_id),
            )
            affected = cursor.rowcount
        connection.commit()
    if affected == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
