"""Incremental, idempotent export of redacted generation-job metadata to Delta.

PySpark is imported lazily inside functions (not at module scope) so this
module can be imported — and its pure-Python helpers unit tested — in an
environment without a Spark runtime, such as CI's plain unit-test job.

`main()`/`run_audit_export` is the wheel-task entry point for Task 3F.1's
audit-export job (`resources/jobs.yml`'s `audit_export_job`). It is only
importable/runnable on a real Databricks cluster (it imports PySpark and the
Databricks runtime's own `spark` session at call time) — this sandbox has
neither, so it has never been executed; `export_completed_jobs`'s pure-Python
siblings remain the only part of this module that's test-covered here.
"""

from __future__ import annotations

import argparse
import hashlib
import os
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


def run_audit_export(*, source_table: str, target_table: str) -> None:
    """Databricks wheel-task entry point: read `source_table`, append new rows.

    `source_table` is expected to already be the Lakebase-federated view/table
    joining `generation_jobs` with the redacted columns `AUDIT_SCHEMA` lists
    (the Lakebase-side read/federation itself is provisioned by Task 1B.2/1B.3
    infra, not by this function). Only importable and runnable inside a
    Databricks Job cluster with a live `spark` session and Unity Catalog
    access — never in this sandbox.
    """

    from pyspark.sql import SparkSession  # local import: only resolvable on a real cluster

    spark = SparkSession.builder.getOrCreate()
    tenant_hash_salt = os.environ["AUDIT_TENANT_HASH_SALT"]
    source_rows = spark.table(source_table)
    row_count = export_completed_jobs(
        spark,
        source_rows=source_rows,
        target_table=target_table,
        tenant_hash_salt=tenant_hash_salt,
    )
    print(f"audit_export: appended {row_count} row(s) to {target_table}")  # noqa: T201


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-table", required=True)
    parser.add_argument("--target-table", required=True)
    args = parser.parse_args()
    run_audit_export(source_table=args.source_table, target_table=args.target_table)


if __name__ == "__main__":
    main()
