"""SSE endpoint: `GET /generation-jobs/:jobId/events`."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.api.sse import stream_job_events

router = APIRouter(prefix="/api/v1/generation-jobs", tags=["events"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


@router.get("/{job_id}/events")
async def get_generation_job_events(
    job_id: UUID, request: Request, user: CurrentUser
) -> EventSourceResponse:
    """Stream this job's redacted generation events.

    Reconnect support: a client that received events up to sequence N sends
    `Last-Event-ID: N` and receives events N+1 onward exactly once, never a
    duplicate or a gap. Authorization is enforced on every poll (via RLS on
    the tenant-scoped connection factory), not only at the initial request.
    """

    last_event_id = int(request.headers.get("last-event-id", "0") or "0")

    def connection_factory() -> object:
        return tenant_connection(user)

    return EventSourceResponse(
        stream_job_events(connection_factory, job_id, last_event_id=last_event_id)
    )
