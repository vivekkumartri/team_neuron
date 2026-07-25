from __future__ import annotations

from uuid import uuid4

import pytest

from story_engine.domain.models import ProgressionMode, ProgressionRequest
from story_engine.services.progression import ProgressionError, target_branch_for_progression


def _request(mode: ProgressionMode, **kwargs: object) -> ProgressionRequest:
    return ProgressionRequest(chapter_id=uuid4(), focal_entity_id=uuid4(), mode=mode, **kwargs)


def test_continue_stays_on_existing_branch() -> None:
    branch_id = uuid4()
    assert target_branch_for_progression(_request(ProgressionMode.CONTINUE), branch_id) == branch_id


@pytest.mark.parametrize(
    "progression_request",
    [
        _request(ProgressionMode.EDIT_TRAITS, trait_change="More trusting"),
        _request(ProgressionMode.REWIND, rewind_to_chapter_id=uuid4()),
    ],
)
def test_branching_modes_require_a_new_branch(progression_request: ProgressionRequest) -> None:
    assert target_branch_for_progression(progression_request, uuid4()) is None


def test_invalid_mode_payload_is_rejected() -> None:
    with pytest.raises(ProgressionError):
        target_branch_for_progression(_request(ProgressionMode.REWIND), uuid4())
