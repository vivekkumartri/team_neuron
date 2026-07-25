# Observability Runbook

## What gets recorded

`src/story_engine/analytics/observability.py` defines `MetricEvent`, a fixed
enum of the metrics/events Task 5I.1 requires: job queue latency, agent
latency, retry count, evaluator outcome, SSE reconnect count, RLS denial
count, deployment version, model spend estimate, budget-threshold-exceeded,
chapter-loop completion, branch creation, trait-edit acceptance, ending-option
use, and a comic-export placeholder for the not-yet-built feature.

Every call to `emit()` carries a `correlation_id` (a UUID shared across all
events for one generation attempt — typically the `generation_jobs.id`) so a
single attempt's queue → agent → evaluator chain can be reconstructed from
logs alone, without a Lakebase query.

## Redaction guarantee

`emit()` calls `_assert_no_forbidden_keys()` before logging anything, which
raises `ForbiddenPayloadKeyError` if the payload contains any of
`FORBIDDEN_PAYLOAD_KEYS` (`prompt`, `secret`, `hidden_characteristic`,
`preference_value`, `raw_response`, `api_key`). This list intentionally
mirrors `FORBIDDEN_COLUMN_SUBSTRINGS` in `analytics/audit_schema.py` so the
two redaction boundaries — the Delta audit export and the operational log
stream — can't silently drift apart. If you need to log something new, check
whether it belongs on this list before adding a call site that logs it.

## Budget kill switch

`enforce_budget(BudgetState)` raises `BudgetExceededError` once
`spend_estimate_usd >= budget_limit_usd` for a user. This only blocks *new*
generation submissions — it never cancels or degrades an in-flight job, and
existing chapters/branches remain fully readable. The error message is
user-facing and states both facts explicitly. Wire this check into the
generation-submission code path (job dispatcher / API route) before relying
on it in production; as of this writing it exists as a library function with
unit coverage but is not yet called from `job_dispatcher.py` or any route.

## Verifying a correlated chain locally

```python
from uuid import uuid4
from story_engine.analytics.observability import CorrelatedLogRecord, MetricEvent, emit

job_id = uuid4()
emit(CorrelatedLogRecord(job_id, MetricEvent.JOB_QUEUE_LATENCY, {"seconds": 1.2}))
emit(CorrelatedLogRecord(job_id, MetricEvent.AGENT_LATENCY, {"seconds": 3.4}))
```

Both records will carry `correlation_id=str(job_id)` in the emitted log
record's `extra` fields — grep Databricks App logs for that id to reconstruct
the chain.

## Known gaps (not yet done)

- No OpenTelemetry exporter is wired up; `emit()` uses the standard library
  `logging` module only. An OTel-compatible exporter should wrap or replace
  this before relying on distributed tracing across the App/Job boundary.
- No caller in `job_dispatcher.py`, the worker entry points, or any API route
  actually calls `emit()` or `enforce_budget()` yet — this module is a tested,
  ready-to-use library, not yet integrated into the generation pipeline.
- Per-user budget limits have no storage/configuration surface (no
  `budget_limit_usd` column or settings endpoint exists yet).
