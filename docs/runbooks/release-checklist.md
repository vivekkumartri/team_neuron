# Production Release Checklist and Rollback Gate

## Pre-deploy checklist (all required before triggering `deploy.yml` with `target: prod`)

- [ ] `pytest -q` passes on the commit being released (unit + contract +
      security tests that don't need a live DB).
- [ ] `pytest tests/security/test_rls_negative.py tests/security/test_personalization_isolation.py -q`
      passes against a staging database (`TEST_DATABASE_URL` pointed at a
      real Lakebase branch, not skipped).
- [ ] `ruff check .` and `mypy src/story_engine` pass with zero findings.
- [ ] `python scripts/check_task_paths.py` reports no target-file collisions.
- [ ] `databricks bundle validate -t prod` succeeds.
- [ ] A migration backup/restore has been validated on the target database
      (restore a recent backup to a scratch database and confirm
      `scripts/migrate.py`'s idempotency check passes against it) —
      **not yet exercised in this repo; no live Lakebase instance exists in
      this development sandbox.**
- [ ] Staged deploy to `staging` completed and its App health check
      (`GET /api/v1/readiness`) returns healthy.
- [ ] A worker job run (`generation_job`) completed successfully in
      `staging` after the staged deploy.
- [ ] Audit-export data-quality check (`notebooks/03_operational_quality_checks.py`)
      ran clean against `staging`.
- [ ] Release evidence (test reports, bundle version, health-check output)
      attached to the release pull request.
- [ ] Manual approval recorded in the GitHub Environment's protection rule
      for `prod` (configured in repo settings, not in this file).

## Rollback gate

Rollback is **always** an application/bundle version rollback — redeploy the
last known-good bundle version via
`databricks bundle deploy -t prod --version <known-good-version>` (verify
the exact flag against the Databricks CLI version in use). Rollback **never**
deletes or reverts published canon data (`chapters`, `branch_entity_states`,
`canon_events`, etc.) — see `docs/runbooks/rollback.md` for the full
procedure and its rationale.

## Deferred scope (not in this release)

Per Task 5.S1, explicitly deferred and tracked as follow-up work rather than
release blockers:

- Image/comic generation and export (the frontend already renders these as
  non-operable "Coming later" states per the prototype-boundary note in
  task.md's Track H section).
- Animated portraits.
- Multi-author collaboration on a single story.
- Vector retrieval / semantic search over story history.

## Known gaps in this checklist as of this pass

- The migration backup/restore validation, staged App health check, worker
  job run, and audit-quality-check items above have never actually been
  performed — there is no Databricks workspace or Lakebase instance in this
  project's development sandbox. This checklist and `deploy.yml`'s `gate`
  job are the mechanism; a first real staging rehearsal (with rollback
  rehearsal, capturing deployed bundle version and restoration evidence per
  Task 5J.3's verification bullet) has not happened yet.
- Quota defaults and model budget thresholds referenced in Task 5.S1 have no
  concrete values recorded anywhere in this repo yet (the budget kill switch
  in `analytics/observability.py` has no configured `budget_limit_usd`
  source) — this checklist cannot yet be signed off end-to-end.
