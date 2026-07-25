# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Redacted audit Delta sink smoke test (Task 1B.3)
# MAGIC
# MAGIC Creates the append-only `generation_audit` Delta table (if absent) and
# MAGIC asserts it contains none of the forbidden column patterns — prose,
# MAGIC hidden characteristics, user preferences, prompts, or raw agent payloads
# MAGIC must never reach Unity Catalog.

# COMMAND ----------
from story_engine.analytics.audit_export import create_generation_audit_table
from story_engine.analytics.audit_schema import FORBIDDEN_COLUMN_SUBSTRINGS

dbutils.widgets.text("catalog_name", "story_engine", "Unity Catalog catalog")
dbutils.widgets.text("schema_name", "app_audit", "Audit schema")
dbutils.widgets.text("table_name", "generation_audit", "Audit table name")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
table_name = dbutils.widgets.get("table_name")
full_table = f"{catalog_name}.{schema_name}.{table_name}"

# COMMAND ----------
create_generation_audit_table(spark, table=full_table)

# COMMAND ----------
# Verification (Task 1B.3 acceptance): DESCRIBE HISTORY succeeds, and a
# schema assertion confirms every forbidden pattern is absent from the
# actual deployed table, not just from the Python-side schema constant.
history = spark.sql(f"DESCRIBE HISTORY {full_table}").collect()
assert len(history) >= 1, "expected at least the CREATE TABLE history entry"

actual_columns = [field.name.lower() for field in spark.table(full_table).schema.fields]
for column in actual_columns:
    for forbidden in FORBIDDEN_COLUMN_SUBSTRINGS:
        assert forbidden not in column, (
            f"forbidden pattern {forbidden!r} found in deployed column {column!r}"
        )

print(f"Table {full_table} has {len(actual_columns)} columns, none forbidden.")
print("Audit Delta sink smoke test: PASS")
