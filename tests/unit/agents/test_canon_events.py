from __future__ import annotations

from uuid import uuid4

import pytest

from story_engine.domain.models import CanonEventStatus
from story_engine.services.canon_events import (
    CanonEventTransitionError,
    CanonEventType,
    SuggestedRelationship,
    build_introduce_entity_request,
    ensure_canon_event_transition,
    requires_target_entity,
)
from story_engine.services.endings import (
    EndingReadinessInputs,
    is_ending_eligible,
    manual_ending_request_allowed,
)
from story_engine.services.revisions import (
    RevisionInvariantError,
    RevisionRequest,
    approve_revision,
    ensure_revision_invariant,
)
from story_engine.services.trait_states import (
    TraitEditRejected,
    TraitEditRequest,
    TraitEditSource,
    requires_new_child_branch,
)


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        (CanonEventType.KILL, True),
        (CanonEventType.REVIVE, True),
        (CanonEventType.MOVE_REALM, True),
        (CanonEventType.INTRODUCE_ENTITY, False),
        (CanonEventType.EDIT_CANON, False),
    ],
)
def test_requires_target_entity(event_type: CanonEventType, expected: bool) -> None:
    assert requires_target_entity(event_type) is expected


def test_valid_and_invalid_transitions() -> None:
    ensure_canon_event_transition(CanonEventStatus.DRAFT, CanonEventStatus.EVALUATING)
    ensure_canon_event_transition(CanonEventStatus.EVALUATING, CanonEventStatus.APPROVED)
    with pytest.raises(CanonEventTransitionError):
        ensure_canon_event_transition(CanonEventStatus.APPROVED, CanonEventStatus.EVALUATING)


def test_introduce_entity_carries_suggested_relationships() -> None:
    request = build_introduce_entity_request(
        branch_id=uuid4(),
        proposed_payload={"name": "Vane"},
        suggested_relationships=[
            SuggestedRelationship(to_entity_id=uuid4(), relationship_type="RIVAL_OF", confidence=0.6)
        ],
    )
    assert request.event_type is CanonEventType.INTRODUCE_ENTITY
    assert len(request.proposed_payload["suggested_relationships"]) == 1


def test_ending_eligibility_requires_all_three_inputs_to_be_strong() -> None:
    weak = EndingReadinessInputs(
        published_chapter_count=1, business_pacing_score=40, open_thread_resolution_ratio=0.2
    )
    assert not is_ending_eligible(weak)

    strong = EndingReadinessInputs(
        published_chapter_count=6, business_pacing_score=90, open_thread_resolution_ratio=0.9
    )
    assert is_ending_eligible(strong)


def test_manual_ending_request_gated_by_minimum_chapter_count() -> None:
    assert not manual_ending_request_allowed(2)
    assert manual_ending_request_allowed(3)


def test_revision_invariant_rejects_approved_without_branch() -> None:
    revision = RevisionRequest(chapter_id=uuid4(), author_patch="tighten the dialogue")
    with pytest.raises(RevisionInvariantError):
        ensure_revision_invariant(revision.model_copy(update={"status": CanonEventStatus.APPROVED}))

    approved = approve_revision(revision, replacement_branch_id=uuid4())
    assert approved.replacement_branch_id is not None


def test_go_with_the_flow_never_forks_but_edits_always_do() -> None:
    branch_id, character_id = uuid4(), uuid4()
    flow = TraitEditRequest(branch_id=branch_id, character_id=character_id, source=TraitEditSource.GO_WITH_THE_FLOW)
    assert requires_new_child_branch(flow) is False

    edit = TraitEditRequest(
        branch_id=branch_id,
        character_id=character_id,
        source=TraitEditSource.FREEFORM,
        proposed_traits="more reckless",
    )
    assert requires_new_child_branch(edit) is True

    with pytest.raises(TraitEditRejected):
        requires_new_child_branch(
            TraitEditRequest(branch_id=branch_id, character_id=character_id, source=TraitEditSource.FREEFORM)
        )
