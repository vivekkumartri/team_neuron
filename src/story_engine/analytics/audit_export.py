"""DDL for the append-only redacted Delta audit table (Task 1B.3).

Distinct from `export_generation_audit.py` (Task 3F.3), which incrementally
*populates* this table from Lakebase — this module only owns creating it
with exactly the approved, redacted schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from story_engine.analytics.audit_schema import AUDIT_SCHEMA, assert_schema_is_redacted

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

_SPARK_TYPE_ALIASES = {
    "STRING": "STRING",
    "INT": "INT",
    "BIGINT": "BIGINT",
    "TIMESTAMP": "TIMESTAMP",
}


def _ddl_columns() -> str:
    return ", ".join(
        f"{column} {_SPARK_TYPE_ALIASES[sql_type]}" for column, sql_type in AUDIT_SCHEMA.items()
    )


def create_generation_audit_table(spark: SparkSession, *, table: str) -> None:
    """Create the append-only redacted audit table if it does not already exist."""

    assert_schema_is_redacted()
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {table} ({_ddl_columns()}) "
        "USING DELTA "
        "COMMENT 'Redacted generation-lifecycle audit export. See "
        "src/story_engine/analytics/audit_schema.py for the approved column list — "
        "never add prose, hidden characteristics, preferences, prompts, or raw agent payloads.'"
    )
