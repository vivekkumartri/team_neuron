from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from story_engine.persistence.models import PersonalizationSnapshotRef, StoryCreate


def test_story_rejects_snapshot_owned_by_another_user() -> None:
    with pytest.raises(ValidationError, match="owner"):
        StoryCreate(
            user_id=uuid4(),
            title="A safe story",
            personalization_enabled=True,
            personalization_snapshot=PersonalizationSnapshotRef(
                id=uuid4(), user_id=uuid4(), version=1
            ),
        )


def test_disabled_story_cannot_select_snapshot() -> None:
    user_id = uuid4()
    with pytest.raises(ValidationError, match="Disabled"):
        StoryCreate(
            user_id=user_id,
            title="A safe story",
            personalization_snapshot=PersonalizationSnapshotRef(
                id=uuid4(), user_id=user_id, version=1
            ),
        )
