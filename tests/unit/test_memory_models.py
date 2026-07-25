from __future__ import annotations

from uuid import uuid4

from story_engine.persistence.memory import MemoryReadScope, memory_visibility_predicate


def test_memory_scope_is_bound_to_one_character_and_branch() -> None:
    scope = MemoryReadScope(
        branch_id=uuid4(), character_id=uuid4(), visible_through_chapter_id=uuid4()
    )

    assert memory_visibility_predicate(scope) == (
        scope.branch_id,
        scope.character_id,
        scope.visible_through_chapter_id,
    )
