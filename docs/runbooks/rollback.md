# Runbook: Application / Bundle Rollback

## When to use this

A newly deployed Databricks App version (or bundle deploy) is causing errors,
elevated latency, or incorrect behavior severe enough to revert rather than
fix forward.

## Principle

Rollback is always an **application/bundle version rollback** — redeploying
the previous known-good bundle target. It is **never** a data rollback:
published canon (`chapters`, `branch_entity_states`, `canon_events`, etc.) is
never deleted or reverted as part of an app rollback. If a bad deploy wrote
bad data via a bug, that is a separate, explicit data-remediation decision
made after the app itself is stable again.

## Steps

1. Identify the last known-good deployed bundle version (Databricks Apps
   tracks deployed versions; `databricks bundle deploy` output records the
   version deployed at each step — capture this at every prior deploy so a
   rollback target is always known).
2. Redeploy that version: `databricks bundle deploy -t <target> --version <known-good-version>`
   (exact flag depends on the Databricks CLI version in use — verify against
   `databricks bundle deploy --help` before running in a real incident,
   since this repo has never actually run this command against a live
   workspace).
3. Confirm the App's `/api/v1/health` and `/api/v1/readiness` endpoints
   return healthy after redeploy.
4. Run the RLS negative test and a smoke generation job against the rolled-
   back version before declaring the rollback complete.

## Verification

Capture the redeployed bundle version and the health/readiness check output
as the rollback rehearsal's evidence artifact (see
`docs/runbooks/release-checklist.md`).

## Known gap

This runbook has not been rehearsed against a live workspace — no Databricks
workspace exists in this project's development sandbox yet (see task.md's
earlier note on the interrupted platform-setup steps). Treat the exact CLI
flags above as a starting point to verify, not a tested command.
