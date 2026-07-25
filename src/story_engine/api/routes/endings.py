"""Ending-option listing and selection.

`ending_options` rows are produced by the business/evaluator pipeline once a
branch crosses `ENDING_READINESS_THRESHOLD` (`services/endings.py`) or the
author manually requests them past `MINIMUM_CHAPTERS_BEFORE_MANUAL_REQUEST`
chapters; this route only reads and selects among options that already
exist, it never generates them (that stays a Track E/worker concern).
"""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection

router = APIRouter(prefix="/api/v1/branches", tags=["endings"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class EndingOption(BaseModel):
    id: UUID
    label: str
    summary: str
    selected: bool
    resulting_chapter_id: UUID | None


def _ending_option(row: tuple[Any, ...]) -> EndingOption:
    return EndingOption(
        id=UUID(str(row[0])),
        label=str(row[1]),
        summary=str(row[2]),
        selected=bool(row[3]),
        resulting_chapter_id=UUID(str(row[4])) if row[4] is not None else None,
    )


@router.get("/{branch_id}/ending-options", response_model=list[EndingOption])
def list_ending_options(branch_id: UUID, user: CurrentUser) -> list[EndingOption]:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, label, summary, selected, resulting_chapter_id "
                "FROM ending_options WHERE branch_id = %s ORDER BY created_at",
                (branch_id,),
            )
            rows = cast(list[tuple[Any, ...]], cursor.fetchall())
    return [_ending_option(row) for row in rows]


@router.post(
    "/{branch_id}/ending-options/{option_id}/select",
    response_model=EndingOption,
)
def select_ending_option(branch_id: UUID, option_id: UUID, user: CurrentUser) -> EndingOption:
    """Selecting an ending is exclusive per branch — enforced both here and by

    the partial unique index `ending_options_one_selected_idx` (migration
    0009), so a concurrent double-select fails at the database rather than
    silently producing two "selected" endings.
    """

    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ending_options SET selected = false "
                "WHERE branch_id = %s AND selected AND id != %s",
                (branch_id, option_id),
            )
            cursor.execute(
                "UPDATE ending_options SET selected = true "
                "WHERE id = %s AND branch_id = %s "
                "RETURNING id, label, summary, selected, resulting_chapter_id",
                (option_id, branch_id),
            )
            row = cursor.fetchone()
        if row is None:
            # Roll back the unselect above too — a 404 must never have a side
            # effect on the previously selected option.
            connection.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ending option not found"
            )
        connection.commit()
    return _ending_option(cast(tuple[Any, ...], row))
