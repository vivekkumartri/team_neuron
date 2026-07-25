from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from story_engine.persistence.jobs import GenerationJobSubmit


def test_job_submission_requires_a_nontrivial_idempotency_key() -> None:
    with pytest.raises(ValidationError):
        GenerationJobSubmit(
            branch_id=uuid4(), requested_by_user_id=uuid4(), idempotency_key="short"
        )
