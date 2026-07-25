# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Lakebase smoke test (Task 1B.2)
# MAGIC
# MAGIC Confirms the `dev` Lakebase project/branch is reachable using a non-owner
# MAGIC role, that the bootstrap migration (`migrations/0001_bootstrap.sql`) has
# MAGIC been applied, and that the connecting role is not the database owner.
# MAGIC
# MAGIC This notebook is read-only diagnostics. It must never print a password,
# MAGIC OAuth token, or connection string — only `current_user`, `current_database`,
# MAGIC and row counts.

# COMMAND ----------
import psycopg
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("lakebase_endpoint", "", "Lakebase endpoint resource name")
dbutils.widgets.text("database_name", "", "Lakebase database name")
dbutils.widgets.text("database_host", "", "Lakebase host")
dbutils.widgets.text("database_user", "", "Non-owner application role")

endpoint = dbutils.widgets.get("lakebase_endpoint")
database_name = dbutils.widgets.get("database_name")
database_host = dbutils.widgets.get("database_host")
database_user = dbutils.widgets.get("database_user")

assert endpoint and database_name and database_host and database_user, (
    "All four widget values are required; this notebook does not fall back to "
    "hard-coded connection details."
)

# COMMAND ----------
# Databricks mints a short-lived OAuth database credential; it is never
# written to notebook output, a variable that survives the cell, or a file.
credential = WorkspaceClient().postgres.generate_database_credential(endpoint=endpoint)

with psycopg.connect(
    dbname=database_name,
    user=database_user,
    host=database_host,
    port="5432",
    sslmode="require",
    password=credential.token,
    connect_timeout=5,
) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT current_user, current_database()")
        current_user, current_database = cur.fetchone()

        # Task 1B.2 acceptance: confirm the connecting identity is not the
        # database owner role.
        cur.execute(
            "SELECT rolname FROM pg_authid WHERE oid = ("
            "  SELECT datdba FROM pg_database WHERE datname = current_database())"
        )
        owner_role = cur.fetchone()[0]
        assert current_user != owner_role, (
            f"connected as owner role {current_user!r}; smoke check requires a "
            "non-owner application role"
        )

        # Confirm the bootstrap migration has been applied.
        cur.execute(
            "SELECT to_regclass('public.schema_migrations') IS NOT NULL"
        )
        (bootstrap_applied,) = cur.fetchone()
        assert bootstrap_applied, (
            "schema_migrations table is missing; run scripts/migrate.py before "
            "this smoke test"
        )

        cur.execute("SELECT count(*) FROM schema_migrations")
        (applied_count,) = cur.fetchone()

print(f"current_user={current_user!r} (owner_role={owner_role!r}, non-owner confirmed)")
print(f"current_database={current_database!r}")
print(f"applied_migrations={applied_count}")
print("Lakebase smoke test: PASS")
