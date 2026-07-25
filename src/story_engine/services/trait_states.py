"""Versioned, branch-scoped trait-state edits (Edit-traits progression mode)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TraitEditSource(StrEnum):
    SUGGESTED = "SUGGESTED"
    FREEFORM = "FREEFORM"
    GO_WITH_THE_FLOW = "GO_WITH_THE_FLOW"


class TraitEditRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    branch_id: UUID
    character_id: UUID
    source: TraitEditSource
    proposed_traits: str | None = Field(default=None, max_length=2_000)


class TraitEditRejected(ValueError):
    """A trait-edit request does not create a new branch-scoped version."""


def next_trait_state_version(current_version: int) -> int:
    if current_version < 0:
        raise ValueError("current_version cannot be negative")
    return current_version + 1


def requires_new_child_branch(request: TraitEditRequest) -> bool:
    """"Go with the flow" makes no change and must not fork a branch; any
    actual trait change (suggested or freeform) is branch-scoped and requires
    a validated child branch (design.md: "on approval it creates a child
    branch with a versioned trait/relationship state snapshot").
    """

    if request.source is TraitEditSource.GO_WITH_THE_FLOW:
        if request.proposed_traits:
            raise TraitEditRejected("Go-with-the-flow must not carry a proposed trait change")
        return False
    if not request.proposed_traits:
        raise TraitEditRejected(f"{request.source} requires proposed_traits text")
    return True
