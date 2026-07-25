"""Data-quality and reconciliation checks (Task 5I.2).

Pure-Python check functions operating on plain rows so they're unit-testable
without a live Spark/Postgres runtime — `notebooks/03_operational_quality_checks.py`
is the thin Databricks Job wrapper that fetches real rows and calls these.
Every failure carries an actionable identifier (a chapter/branch/job id, not
just "check failed") per this task's verification bullet.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from story_engine.analytics.audit_schema import FORBIDDEN_COLUMN_SUBSTRINGS


@dataclass(frozen=True)
class QualityCheckFailure:
    check_name: str
    identifier: str
    detail: str


@dataclass(frozen=True)
class ChapterRow:
    chapter_id: UUID
    branch_id: UUID
    status: str  # matches domain.models.ChapterStatus values


@dataclass(frozen=True)
class BranchStateRow:
    branch_id: UUID
    has_published_chapter: bool


def check_published_chapter_state_consistency(
    chapters: list[ChapterRow],
) -> list[QualityCheckFailure]:
    """Every PUBLISHED chapter's branch must have at least one published

    chapter recorded in branch state — a mismatch means state and chapters
    have diverged.
    """

    failures: list[QualityCheckFailure] = []
    published_branch_ids = {row.branch_id for row in chapters if row.status == "PUBLISHED"}
    seen_branch_ids = {row.branch_id for row in chapters}
    for branch_id in published_branch_ids - seen_branch_ids:
        failures.append(
            QualityCheckFailure(
                check_name="published_chapter_state_consistency",
                identifier=str(branch_id),
                detail="Branch has a PUBLISHED chapter reference with no matching chapter row",
            )
        )
    return failures


@dataclass(frozen=True)
class BranchAncestryRow:
    branch_id: UUID
    parent_branch_id: UUID | None


def check_branch_ancestry_validity(branches: list[BranchAncestryRow]) -> list[QualityCheckFailure]:
    """Every non-null parent must exist, and there must be no ancestry cycle."""

    failures: list[QualityCheckFailure] = []
    by_id = {row.branch_id: row for row in branches}

    for row in branches:
        if row.parent_branch_id is not None and row.parent_branch_id not in by_id:
            failures.append(
                QualityCheckFailure(
                    check_name="branch_ancestry_validity",
                    identifier=str(row.branch_id),
                    detail=f"parent_branch_id {row.parent_branch_id} does not exist",
                )
            )

    for row in branches:
        visited: set[UUID] = set()
        current: BranchAncestryRow | None = row
        while current is not None and current.parent_branch_id is not None:
            if current.branch_id in visited:
                failures.append(
                    QualityCheckFailure(
                        check_name="branch_ancestry_validity",
                        identifier=str(row.branch_id),
                        detail="Ancestry cycle detected",
                    )
                )
                break
            visited.add(current.branch_id)
            current = by_id.get(current.parent_branch_id)

    return failures


def check_event_sequence_continuity(
    job_id: UUID, sequences: list[int]
) -> list[QualityCheckFailure]:
    """`generation_events.sequence` must be gapless starting at 1 for a given job."""

    ordered = sorted(sequences)
    expected = list(range(1, len(ordered) + 1))
    if ordered != expected:
        return [
            QualityCheckFailure(
                check_name="event_sequence_continuity",
                identifier=str(job_id),
                detail=f"Expected sequences {expected}, found {ordered}",
            )
        ]
    return []


def check_audit_export_reconciliation(
    *, source_row_count: int, exported_row_count: int, job_id: UUID
) -> list[QualityCheckFailure]:
    if source_row_count != exported_row_count:
        return [
            QualityCheckFailure(
                check_name="audit_export_reconciliation",
                identifier=str(job_id),
                detail=(
                    f"Source has {source_row_count} completed jobs but the audit export has "
                    f"{exported_row_count}"
                ),
            )
        ]
    return []


def check_no_forbidden_delta_columns(
    table_name: str, columns: list[str]
) -> list[QualityCheckFailure]:
    failures: list[QualityCheckFailure] = []
    for column in columns:
        lowered = column.lower()
        for forbidden in FORBIDDEN_COLUMN_SUBSTRINGS:
            if forbidden in lowered:
                failures.append(
                    QualityCheckFailure(
                        check_name="no_forbidden_delta_columns",
                        identifier=table_name,
                        detail=f"Column {column!r} matches forbidden substring {forbidden!r}",
                    )
                )
    return failures
