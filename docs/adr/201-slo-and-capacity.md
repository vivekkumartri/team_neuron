# ADR 201: Dev/Staging SLOs and Capacity Targets

## Status

Proposed — documented targets, not yet validated against a live deployment
(no Databricks workspace exists in this project's development environment as
of this writing; see task.md's earlier note on the interrupted platform-setup
steps).

## Context

Task 5J.2 requires explicit SLOs before performance/resilience testing can
declare pass/fail. Without a stated threshold, a load-test report has no way
to distinguish "acceptable" from "regression."

## Decision

For the `dev`/`staging` environments (not production, which may set tighter
or separately-reviewed targets):

| Metric | Target | Measured by |
|---|---|---|
| API request latency (read endpoints) | p95 < 500ms | `tests/performance/api_load.js` |
| SSE reconnect round-trip | p95 < 1000ms | `tests/performance/sse_reconnect.js` |
| Job queue start (submit → `LEASED`) | p95 < 10s | Manual timing against `generation_jobs.leased_at - created_at` |
| Generation completion (submit → `SUCCEEDED`) | p95 < 90s | Manual timing against `generation_jobs.status` transitions |
| Error rate under load | < 1% non-2xx/3xx/401/404 | k6 `http_req_failed` threshold |
| Concurrent users (dev capacity target) | 20 concurrent | `api_load.js`'s `ramping-vus` scenario |

## Consequences

- These numbers are a starting point for the first staging rehearsal, not a
  contractually validated SLA. They should be revisited once
  `tests/performance/*.js` actually run against a real deployment.
- Job queue start and generation completion currently have no automated k6
  script — they require a live `generation_jobs` row lifecycle to observe,
  which needs the worker/job infrastructure actually deployed
  (`resources/jobs.yml`) rather than a synthetic HTTP load generator.
- No duplicate-canon-commit test under retry/load has been run yet; the
  idempotency guarantee this depends on (outbox pattern,
  `SELECT ... FOR UPDATE SKIP LOCKED` leasing) is unit/integration tested in
  `tests/integration/workers/test_queue.py`, but never exercised under actual
  concurrent load.

## Known gap

Every number in this table is a design target, not a measured result. Do not
cite this ADR as evidence of achieved performance — cite it as the bar a
future load-test run must clear.
