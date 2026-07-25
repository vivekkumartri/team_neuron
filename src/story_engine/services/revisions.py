"""Published-screenplay revisions: always a replacement child branch, never an in-place edit."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from story_engine.domain.models import CanonEventStatus


class RevisionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter_id: UUID
    author_patch: str = Field(min_length=1, max_length=12_000)
    status: CanonEventStatus = CanonEventStatus.DRAFT
    replacement_branch_id: UUID | None = None


class RevisionInvariantError(ValueError):
    """A revision violated the 'approved implies replacement branch' invariant."""


def ensure_revision_invariant(revision: RevisionRequest) -> None:
    """Mirrors the DB CHECK in migration 0009: an APPROVED revision must
    always carry a replacement_branch_id, and only an APPROVED revision may.
    """

    is_approved = revision.status is CanonEventStatus.APPROVED
    has_branch = revision.replacement_branch_id is not None
    if is_approved and not has_branch:
        raise RevisionInvariantError("An approved revision must have a replacement branch")
    if not is_approved and has_branch:
        raise RevisionInvariantError("Only an approved revision may reference a replacement branch")


def approve_revision(revision: RevisionRequest, *, replacement_branch_id: UUID) -> RevisionRequest:
    approved = revision.model_copy(
        update={"status": CanonEventStatus.APPROVED, "replacement_branch_id": replacement_branch_id}
    )
    ensure_revision_invariant(approved)
    return approved
