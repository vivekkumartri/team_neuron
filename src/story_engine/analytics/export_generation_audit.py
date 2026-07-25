"""Incremental, idempotent export of redacted generation-job metadata to Delta.

PySpark is imported lazily inside functions (not at module scope) so this
module can be imported — and its pure-Python helpers unit tested — in an
environment without a Spark runtime, such as CI's plain unit-test job.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from story_engine.analytics.audit_schema import AUDIT_SCHEMA, assert_schema_is_redacted

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession


def hash_tenant_id(user_id: str, *, salt: str) -> str:
    """One-way tenant identifier for the audit table (never the raw user_id)."""

    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()


@dataclass(frozen=True)
class HighWaterMark:
    table: str
    last_exported_at: datetime | None


def read_high_water_mark(spark: SparkSession, *, table: str) -> HighWaterMark:
    """Read the last-exported timestamp; absent on first run."""

    if not spark.catalog.tableExists(table):
        return HighWaterMark(table=table, last_exported_at=None)
    row = spark.sql(f"SELECT max(created_at) AS last_at FROM {table}").first()
    last_at = row["last_at"] if row is not None else None
    return HighWaterMark(table=table, last_exported_at=last_at)


def export_completed_jobs(
    spark: SparkSession,
    *,
    source_rows: DataFrame,
    target_table: str,
    tenant_hash_salt: str,
) -> int:
    """Append only new completed-job rows since the last high-water mark.

    `source_rows` is expected to already be a Lakebase JDBC/foreachPartition
    read limited to `generation_jobs` joined with the redacted fields listed
    in `AUDIT_SCHEMA`; this function only owns the idempotent append and
    schema assertion, not the Lakebase read itself (kept separate so the
    read's connection/auth concerns don't leak into export logic).
    """

    assert_schema_is_redacted()
    watermark = read_high_water_mark(spark, table=target_table)

    incremental = source_rows
    if watermark.last_exported_at is not None:
        incremental = incremental.filter(source_rows.created_at > watermark.last_exported_at)

    missing_columns = set(AUDIT_SCHEMA) - set(incremental.columns)
    if missing_columns:
        raise ValueError(
            f"source_rows is missing approved audit columns: {sorted(missing_columns)}"
        )
    extra_columns = set(incremental.columns) - set(AUDIT_SCHEMA)
    if extra_columns:
        raise ValueError(
            f"source_rows has unapproved columns not in AUDIT_SCHEMA: {sorted(extra_columns)}"
        )

    row_count = int(incremental.count())
    if row_count == 0:
        return 0

    incremental.select(*AUDIT_SCHEMA.keys()).write.format("delta").mode("append").saveAsTable(
        target_table
    )
    return row_count
