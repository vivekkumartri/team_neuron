# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Platform bootstrap (Task 1B.1)
# MAGIC
# MAGIC Creates the Unity Catalog catalog/schema/volume boundaries and the Delta
# MAGIC audit table namespace for one environment. Idempotent — safe to re-run.
# MAGIC Transactional request data (users, stories, branches, jobs, ...) lives in
# MAGIC Lakebase, never here; this notebook only touches governed Unity Catalog
# MAGIC objects used for redacted analytics/audit export (Task 1B.3/3F.3).

# COMMAND ----------
dbutils.widgets.text("catalog_name", "story_engine", "Unity Catalog catalog")
dbutils.widgets.text("schema_name", "app", "Schema (per environment)")
dbutils.widgets.text("volume_name", "artifacts", "Approved-artifacts volume")

catalog_name = dbutils.widgets.get("catalog_name")
schema_name = dbutils.widgets.get("schema_name")
volume_name = dbutils.widgets.get("volume_name")

# COMMAND ----------
spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog_name}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog_name}.{schema_name}")
spark.sql(
    f"CREATE VOLUME IF NOT EXISTS {catalog_name}.{schema_name}.{volume_name} "
    "COMMENT 'Approved artifacts and future export files only — no raw model payloads.'"
)

# COMMAND ----------
# Delta audit table namespace (Task 1B.3 creates the actual redacted table;
# this only guarantees the schema it lives in exists before that task runs).
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog_name}.{schema_name}_audit")

# COMMAND ----------
# Verification (Task 1B.1 acceptance): list what now exists.
schemas = [row["databaseName"] for row in spark.sql(f"SHOW SCHEMAS IN {catalog_name}").collect()]
assert schema_name in schemas, f"expected schema {schema_name!r} in {schemas}"
assert f"{schema_name}_audit" in schemas, f"expected audit schema in {schemas}"

volume_path = f"/Volumes/{catalog_name}/{schema_name}/{volume_name}"
dbutils.fs.ls(volume_path)  # raises if the volume isn't actually reachable

print(f"Catalog {catalog_name!r} ready with schemas {schemas!r}")
print(f"Volume ready at {volume_path}")
print("Platform bootstrap: PASS")
