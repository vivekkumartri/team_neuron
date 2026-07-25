# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Operational data-quality and reconciliation checks (Task 5I.2)
# MAGIC
# MAGIC Scheduled Databricks Job wrapper around the pure-Python check functions in
# MAGIC `story_engine.analytics.quality_checks` (unit-tested in
# MAGIC `tests/unit/analytics/test_quality_checks.py` without needing a live
# MAGIC Spark/Postgres session). This notebook's only job is fetching real rows
# MAGIC and handing them to those functions — the check logic itself lives in the
# MAGIC importable module so it's testable outside a notebook runtime.
# MAGIC
# MAGIC Run as a scheduled Databricks Job (see `resources/jobs.yml` for the
# MAGIC pattern used by `generation_job`/`report_job` — a `quality_checks_job`
# MAGIC resource following that same shape has not yet been added there; see
# MAGIC task.md Task 5I.2 status note).

# COMMAND ----------
dbutils.widgets.text("lakebase_endpoint", "", "Lakebase endpoint")  # noqa: F821
dbutils.widgets.text("lakebase_database", "story_engine", "Database name")  # noqa: F821
dbutils.widgets.text("audit_catalog_table", "story_engine.audit.generation_audit", "Audit table")  # noqa: F821

# COMMAND ----------
from uuid import UUID  # noqa: E402

from story_engine.analytics.quality_checks import (  # noqa: E402
    BranchAncestryRow,
    ChapterRow,
    QualityCheckFailure,
    check_audit_export_reconciliation,
    check_branch_ancestry_validity,
    check_event_sequence_continuity,
    check_no_forbidden_delta_columns,
    check_published_chapter_state_consistency,
)

# COMMAND ----------
# In a real run these come from Lakebase (via the same
# `generate_database_credential`-based connection pattern as
# `01_lakebase_smoke_test.py`) and from `spark.table(audit_catalog_table)`.
# This notebook has never been executed against a live workspace — there is
# no Databricks workspace available in the sandbox this was authored in.
chapters: list[ChapterRow] = []
branches: list[BranchAncestryRow] = []
event_sequences_by_job: dict[UUID, list[int]] = {}
audit_reconciliation_counts: list[tuple[UUID, int, int]] = []  # (job_id, source, exported)
delta_columns: list[str] = []

# COMMAND ----------
all_failures: list[QualityCheckFailure] = []
all_failures += check_published_chapter_state_consistency(chapters)
all_failures += check_branch_ancestry_validity(branches)
for job_id, sequences in event_sequences_by_job.items():
    all_failures += check_event_sequence_continuity(job_id, sequences)
for job_id, source_count, exported_count in audit_reconciliation_counts:
    all_failures += check_audit_export_reconciliation(
        source_row_count=source_count, exported_row_count=exported_count, job_id=job_id
    )
all_failures += check_no_forbidden_delta_columns("generation_audit", delta_columns)

# COMMAND ----------
if all_failures:
    for failure in all_failures:
        print(f"[{failure.check_name}] {failure.identifier}: {failure.detail}")  # noqa: T201
    raise SystemExit(f"{len(all_failures)} data-quality check(s) failed — see output above.")

print("All data-quality checks passed.")  # noqa: T201
