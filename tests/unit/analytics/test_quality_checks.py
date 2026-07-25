"""Task 5I.2 acceptance: inject a broken fixture, check fails with an

actionable identifier; a clean fixture passes.
"""

from __future__ import annotations

from uuid import uuid4

from story_engine.analytics.quality_checks import (
    BranchAncestryRow,
    ChapterRow,
    check_audit_export_reconciliation,
    check_branch_ancestry_validity,
    check_event_sequence_continuity,
    check_no_forbidden_delta_columns,
    check_published_chapter_state_consistency,
)


def test_published_chapter_state_consistency_clean_fixture_passes() -> None:
    branch_id = uuid4()
    chapters = [ChapterRow(chapter_id=uuid4(), branch_id=branch_id, status="PUBLISHED")]
    assert check_published_chapter_state_consistency(chapters) == []


def test_branch_ancestry_missing_parent_fails_with_identifier() -> None:
    orphan_branch = uuid4()
    missing_parent = uuid4()
    branches = [BranchAncestryRow(branch_id=orphan_branch, parent_branch_id=missing_parent)]
    failures = check_branch_ancestry_validity(branches)
    assert len(failures) == 1
    assert failures[0].identifier == str(orphan_branch)
    assert failures[0].check_name == "branch_ancestry_validity"


def test_branch_ancestry_cycle_is_detected() -> None:
    a, b = uuid4(), uuid4()
    branches = [
        BranchAncestryRow(branch_id=a, parent_branch_id=b),
        BranchAncestryRow(branch_id=b, parent_branch_id=a),
    ]
    failures = check_branch_ancestry_validity(branches)
    assert any(f.detail == "Ancestry cycle detected" for f in failures)


def test_branch_ancestry_clean_fixture_passes() -> None:
    root, child = uuid4(), uuid4()
    branches = [
        BranchAncestryRow(branch_id=root, parent_branch_id=None),
        BranchAncestryRow(branch_id=child, parent_branch_id=root),
    ]
    assert check_branch_ancestry_validity(branches) == []


def test_event_sequence_gap_fails_with_job_id() -> None:
    job_id = uuid4()
    failures = check_event_sequence_continuity(job_id, [1, 2, 4])
    assert len(failures) == 1
    assert failures[0].identifier == str(job_id)


def test_event_sequence_continuous_passes() -> None:
    assert check_event_sequence_continuity(uuid4(), [1, 2, 3]) == []


def test_audit_export_reconciliation_mismatch_fails() -> None:
    job_id = uuid4()
    failures = check_audit_export_reconciliation(
        source_row_count=10, exported_row_count=8, job_id=job_id
    )
    assert len(failures) == 1
    assert failures[0].identifier == str(job_id)


def test_audit_export_reconciliation_match_passes() -> None:
    assert check_audit_export_reconciliation(
        source_row_count=10, exported_row_count=10, job_id=uuid4()
    ) == []


def test_forbidden_delta_columns_detected() -> None:
    failures = check_no_forbidden_delta_columns("generation_audit", ["job_id", "prompt_text"])
    assert len(failures) == 1
    assert failures[0].identifier == "generation_audit"


def test_no_forbidden_delta_columns_clean_fixture_passes() -> None:
    assert check_no_forbidden_delta_columns("generation_audit", ["job_id", "status"]) == []
