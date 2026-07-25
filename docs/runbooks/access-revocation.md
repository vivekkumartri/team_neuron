# Runbook: User Preference Deletion and Access Revocation

## User preference deletion

`DELETE /api/v1/me/preferences/{id}` (`api/routes/preferences.py`) sets
`revoked_at = now()` rather than hard-deleting the row — `list_preferences`
already filters `WHERE revoked_at IS NULL`, so a revoked preference stops
being read or included in any *new* `personalization_snapshots` immediately.

Existing, already-created snapshots are immutable by design
(`personalization_snapshots` is append-only per `create_personalization_snapshot`)
and are **not** retroactively edited by a later preference revocation — a
generation job that already read a snapshot before the revocation keeps
using what it read. If a user needs a previously generated snapshot actually
purged (not just excluded from future snapshots), that is a manual data-
deletion request, handled separately from the self-service revocation
endpoint, since it may affect published chapters that already incorporated
that personalization.

## Revoking a compromised service-principal or user credential

1. Databricks Apps/Jobs run as a deployment identity (see
   `resources/permissions.yml`'s documented service-principal grants) — a
   compromised credential is revoked at the Databricks account level
   (rotate the service principal's OAuth secret or disable the principal),
   not by editing anything in this repo.
2. For a compromised human user's session: Databricks Apps identity is
   asserted via `x-forwarded-user`/`x-forwarded-email` at the platform
   proxy layer (`api/auth.py`'s `authenticate_request`) — revoking workspace
   access for that user in the Databricks account console immediately stops
   new authenticated requests from succeeding for them.
3. Confirm no lingering Lakebase OAuth token remains valid past its stated
   TTL by checking `WorkspaceClient().postgres.generate_database_credential`
   documentation for the actual expiry window in use.

## Verification

After revocation, attempt the previously-valid identity against
`/api/v1/health` (unauthenticated, should still succeed) and
`/api/v1/stories` (authenticated, should now return 401) to confirm the
access path is actually closed.

## Known gap

This has not been exercised against a live workspace — no Databricks
workspace exists in this project's sandbox. The JIT-provisioning and
`x-forwarded-*` header trust model in `auth.py` is unit/contract-tested
(`tests/contract/test_rest_contract.py`), but the actual proxy-layer identity
assertion has never been verified end-to-end.
