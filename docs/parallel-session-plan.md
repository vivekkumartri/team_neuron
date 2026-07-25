> **Status: all 10 tracks implemented.** See each track's note below for what
> landed and what's still a follow-up. Migration numbers were adjusted from
> the original plan (0010-0012) to 0011-0014 since a real migration
> (`0010_live_generation_commit.sql`) landed concurrently from other work.
> Full verification after integration: 140 tests passing (18 correctly
> skipped, DB-gated), ruff/mypy/`tsc` all clean, no `check_task_paths.py`
> collisions, `databricks bundle validate -t dev` still resolves cleanly.

# Parallel Session Plan — 10 Independent Tracks

Ten sessions that can run at the same time without stepping on each other. Each
track's **Target Files** are exclusive to that track — no two tracks write to
the same file. Where a track needs its own test coverage, it creates a new
test file rather than editing a shared one (e.g. `tests/contract/test_rest_contract.py`
is left alone by everyone; each track adds its own dedicated test file
instead), which is what actually makes 10-way parallelism safe here.

Run `python3 scripts/check_task_paths.py` after merging any subset of these to
confirm no collision slipped in.

---

### Track 1 — Cast-lock and family-tree backend

**Target Files:** `migrations/0010_cast_roster.sql`, `src/story_engine/api/routes/cast.py` (new), `tests/contract/test_cast_contract.py` (new).

Add a `cast_members` table (character id, role, locked_at) and `stories.cast_locked_at`.
Add `POST /stories/{id}/cast-lock` (locks the roster, idempotent — a second
call returns the existing lock rather than erroring) and
`GET /stories/{id}/family-tree` (relationship summary derived from
`branch_relationships` for the story's founding branch). This is the backend
half of the plan's P1.5 item — `web/components/features/onboarding/CastLock.tsx`
currently fakes this with a bare `POST /stories`.

### Track 2 — Idempotency/ETag on canon-event requests

**Target Files:** `src/story_engine/api/routes/world.py`, `tests/contract/test_world_idempotency.py` (new).

Add the same `Idempotency-Key` replay pattern `progression.py` already uses
(check for an existing `canon_event_requests` row with the same
`(requested_by_user_id, idempotency_key)` before inserting) to
`submit_canon_event_request`. Add an `ETag`/`If-Match` header on
`GET /branches/{id}/state` so a stale-write attempt on a follow-up mutation
can be detected client-side (design.md's stale-write guard, still unimplemented
anywhere).

### Track 3 — Idempotency semantics on revision requests

**Target Files:** `src/story_engine/api/routes/revisions.py`, `tests/contract/test_revisions_idempotency.py` (new).

Same replay pattern as Track 2, applied to
`POST /chapters/{id}/revisions` (needs an `idempotency_key` column added to
`chapter_revisions` — coordinate the migration number with Track 1 by
claiming `migrations/0011_revision_idempotency_key.sql` so the two new
migrations don't collide).

### Track 4 — Story/branch context provider (frontend)

**Target Files:** `web/lib/story-context.ts` (new), `web/components/features/stories/StoryList.tsx` (new), `web/components/features/stories/BranchList.tsx` (new).

Build the missing piece every `IdScopedView` text box in `app/page.tsx` is
standing in for: a real list of the caller's stories (`GET /api/v1/stories`)
and, per story, its branches (`GET /api/v1/arcs/{arc_id}/branches`). Export a
`useSelectedBranch()` hook other components can consume. **Do not edit
`app/page.tsx` in this track** — wiring the picker into the route table is a
follow-up integration step once this track's components exist and typecheck
on their own.

### Track 5 — Chapter detail view

**Target Files:** `web/components/features/chapters/ChapterDetailView.tsx` (new).

A page that fetches `GET /chapters/{id}`, renders the published screenplay,
and hosts the already-built (but currently homeless) `RevisionRequestForm`.
Closes the plan's P2.14 gap. Does not touch `app/page.tsx`.

### Track 6 — Archive/unarchive and blocked-generation retry

**Target Files:** `src/story_engine/api/routes/archive.py` (new), `web/components/features/recovery/RecoveryControls.tsx` (new), `migrations/0012_chapter_archive_state.sql` (new).

Backend: `PATCH /chapters/{id}/archive` and `.../unarchive` (soft-state
change only, `chapters.archived_at`, never a delete). A `POST
/generation-jobs/{id}/retry` that re-queues a `BLOCKED`/`FAILED` job via a
fresh `generation_jobs` row + outbox entry (reusing the pattern from
`progression.py` — read it for reference, don't edit it). Frontend:
`RecoveryControls` renders archive/unarchive buttons and a retry button tied
to the job's terminal status.

### Track 7 — Quota and policy-block display

**Target Files:** `src/story_engine/services/quotas.py` (new), `web/components/features/workspace/QuotaBanner.tsx` (new).

Backend: a `QuotaState` model and `check_quota(...)` function (chapters/month,
concurrent branches, etc. — mirror the shape of `services/endings.py`'s
threshold pattern) that a route can call before accepting a progression
request. This is a library module only in this track — wiring it into
`progression.py` is a follow-up, not part of this track, to avoid a
collision. Frontend: a banner component that renders "quota exceeded" /
"approaching limit" copy given a `QuotaState`-shaped prop.

### Track 8 — Observability wiring: job dispatcher

**Target Files:** `src/story_engine/services/job_dispatcher.py`.

Call `analytics.observability.emit()` around `dispatch_pending`'s launch
attempts (`JOB_QUEUE_LATENCY` on enqueue-to-launch time, `RETRY_COUNT` on a
failed launch, `DEPLOYMENT_VERSION` once per process). This is the first
real caller of the observability module built in Task 5I.1 — right now
nothing invokes it.

### Track 9 — Observability wiring: worker entry points

**Target Files:** `src/story_engine/workers/generation_job.py`, `src/story_engine/workers/report_job.py`.

Call `emit()` for `AGENT_LATENCY`, `CHAPTER_LOOP_COMPLETION`, and
`enforce_budget()` at the point each worker would (once real model calls
exist) make its first paid call — even as a stub, wrapping the
`NotImplementedError` point with a budget check documents where that gate
belongs.

### Track 10 — E2E spec rewrite for the real workspace view

**Target Files:** `tests/e2e/generation.spec.ts`.

The existing spec targets the retired `WorkspaceStudio` demo's DOM shape.
Rewrite it against `WorkspaceView`'s actual markup (chapter-id/focal-entity
inputs, the three `BranchControls` buttons posting to
`/branches/:id/progression`, and the `AgentCoordinationCanvas` +
`ActivityFeed` pairing) so it's accurate even though it still can't run in
this sandbox (no Playwright browser binary available here — see
`task.md` Task 4H.1's note).

---

## After all 10 land

1. One integration pass wires Track 4's story/branch picker and Track 7's
   quota banner into `app/page.tsx` (the one file every track deliberately
   avoided, precisely so it wouldn't collide across 10 parallel sessions).
2. Run `python3 scripts/check_task_paths.py`, the full `pytest -q`, `ruff
   check .`, `mypy src/story_engine`, and `tsc --noEmit -p web/tsconfig.json`.
3. Update `task.md`'s status notes for whichever of P1.5, P1.8, P2.13, P2.14,
   P2.17, P4.22 these tracks closed.

None of these 10 tracks touch the generation pipeline itself (still the
largest remaining item — see `docs/production-readiness-plan.md`) or require
a live Databricks/Lakebase connection to build and unit-test.
