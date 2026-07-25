"""The only supported ways an author advances a published chapter."""

from __future__ import annotations

from uuid import UUID

from story_engine.domain.models import ProgressionMode, ProgressionRequest


class ProgressionError(ValueError):
    """A progression request does not satisfy its selected mode."""


def target_branch_for_progression(
    request: ProgressionRequest, current_branch_id: UUID
) -> UUID | None:
    """Continue remains on a branch; trait edits and rewind create child branches."""

    if request.mode is ProgressionMode.CONTINUE:
        if request.trait_change or request.rewind_to_chapter_id:
            raise ProgressionError("Continue cannot include a trait change or rewind target")
        return current_branch_id
    if request.mode is ProgressionMode.EDIT_TRAITS:
        if not request.trait_change or request.rewind_to_chapter_id:
            raise ProgressionError("Edit traits requires a trait change and no rewind target")
        return None
    if request.mode is ProgressionMode.REWIND:
        if request.trait_change or not request.rewind_to_chapter_id:
            raise ProgressionError("Rewind requires a target chapter and no trait change")
        return None
    raise ProgressionError("Unsupported progression mode")
