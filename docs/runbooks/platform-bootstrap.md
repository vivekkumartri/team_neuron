# Runbook: Platform bootstrap

Provisions the Unity Catalog boundaries an environment needs before any
application code deploys. Run once per environment (`dev`, then `staging`,
then `prod`), never against more than one environment's catalog at a time.

## Prerequisites

- A Databricks workspace exists with Unity Catalog enabled and a metastore assigned.
- The running identity has `CREATE CATALOG` (or an existing catalog it can `USE CATALOG` /
  `CREATE SCHEMA` on) — see `docs/adr/001-deployment-identities.md` for which identity this
  should be (the administrator identity for first-time catalog creation, not a runtime role).
- `resources/variables.yml`'s `catalog_name`, `schema_name`, and `volume_name` defaults match
  what you intend to create (override per-target with `--var` if not).

## Steps

1. Attach `notebooks/00_platform_setup.py` to a cluster or SQL warehouse in the target
   workspace.
2. Set the notebook widgets to the target environment's catalog/schema/volume names.
3. Run all cells.
4. Confirm the printed output lists both the primary schema and its `_audit` counterpart,
   and that the volume path resolved without error.

## Verification

```
SHOW SCHEMAS IN <catalog>;
-- expect: <schema>, <schema>_audit, plus Unity Catalog defaults

LIST '/Volumes/<catalog>/<schema>/<volume>';
-- expect: succeeds (may be empty on first run)
```

## Rollback

Dropping a catalog/schema here has no effect on Lakebase transactional data —
they are entirely separate systems. If a schema was created with the wrong
name, drop only the empty schema (`DROP SCHEMA IF EXISTS <catalog>.<wrong_schema>`)
and re-run the notebook with corrected widget values. Never drop the catalog
itself once `staging`/`prod` audit history exists in it.
