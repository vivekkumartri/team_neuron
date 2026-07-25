from __future__ import annotations

from uuid import uuid4

from story_engine.persistence.branches import BranchFork, inherited_state_cutoff


def test_fork_state_is_explicitly_bounded_by_parent_chapter() -> None:
    fork = BranchFork(
        parent_branch_id=uuid4(), forked_from_chapter_id=uuid4(), child_name="Storm path"
    )

    assert inherited_state_cutoff(fork) == (fork.parent_branch_id, fork.forked_from_chapter_id)
