# Runbook: Suspected Tenant Isolation / RLS Incident

## Symptom

A user reports seeing another user's story, branch, or chapter content, or a
security test (`tests/security/test_rls_negative.py`) fails against a live
environment.

## Immediate containment

1. Do **not** attempt to "fix forward" by patching data in place — first
   confirm scope.
2. Check `RLS_DENIAL` metric counts (`analytics/observability.py`'s
   `MetricEvent.RLS_DENIAL`) for the affected time window to see whether RLS
   was actually bypassed (an attempted cross-tenant read that was denied) or
   whether a query genuinely returned cross-tenant rows (a real breach).
3. If genuine cross-tenant read is confirmed: revoke the app's Lakebase
   database role's direct table grants immediately (`REVOKE ALL ON ALL
   TABLES IN SCHEMA public FROM <app_role>;`) to stop further reads while
   investigating — the SECURITY DEFINER commit functions remain callable by
   design, so this does not have to take the whole app down, only direct
   table access.

## Diagnosis

1. Check every RLS policy definition against `migrations/0006_rls_and_roles.sql`
   and `migrations/0008_canonical_write_revocation.sql` for the affected
   tables — confirm `set_config('app.user_id', ...)` is actually being
   called before every query (`tenant_connection` in `api/auth.py`).
2. Check whether the affected query path used `tenant_connection` at all, or
   bypassed it with a raw connection.

## Recovery

1. Restore the revoked grants only after the root cause (a missing RLS
   policy, a route that skipped `tenant_connection`, or similar) is fixed
   and covered by a new regression test in `tests/security/test_rls_negative.py`.
2. Never delete the cross-tenant-exposed rows as a "fix" — assess what was
   exposed and to whom, and follow standard incident disclosure practice
   separately from this technical recovery.

## Verification

Re-run `tests/security/test_rls_negative.py` against the affected
environment and confirm cross-tenant reads return zero rows / a 404, not an
error that could itself leak existence information.
