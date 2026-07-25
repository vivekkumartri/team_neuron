# Story Engine — Production Readiness Plan

Status as of this pass: 14 of 43 tracked tasks fully verified (`[x]`), 23 code-complete but unverified against a live environment (`[/]`), 6 not started (`[ ]`, mostly the sync-point tasks that require a real deployment). This document is the single list of what's left, ordered by what actually blocks "every button works in production."

## How to read this

Each item says what's broken or missing, why it matters, and roughly how much work it is. Nothing here is guesswork — it's drawn from the actual `task.md` status notes accumulated while building this, plus a fresh grep pass over the frontend for dead buttons.

---

## P0 — Deploy blockers (nothing works live until these are done)

1. **Get a real deployment target.** Your current Databricks account is Free Edition. That's actually workable (Free Edition supports one Lakebase project, Jobs with a 5-task quota, and up to 3 Apps per the current docs) but has no account-console/service-principal access, so CI/CD must stay manual (`databricks auth login` + `databricks bundle deploy`, run by you, not automated). Action: get your workspace URL, fix `databricks.yml`'s `dev` target host (currently a placeholder from early scaffolding), then run `databricks bundle deploy -t dev`.
2. **Apply migrations to a real Lakebase instance.** All 9 migrations are written and unit-tested for idempotency, but have never run against live Postgres. Action: provision the Lakebase project in the UI, run `scripts/migrate.py` against it, then re-run `tests/integration/persistence/*` with `TEST_DATABASE_URL` set — this is Task 2.S1 in task.md.
3. **Deploy the App and smoke-test it.** Task 4G.1 is code-complete but the App has never actually run — `/api/v1/health` and `/api/v1/readiness` have never been hit outside a local test client. This is Task 4.S1.
4. **Run a seeded Chapter 1 generation end-to-end** (Task 3.S1) — the generation pipeline, worker, and job queue are unit-tested individually but have never fired together against a live job.

Until these four are done, "every button works" is structurally impossible — most of the app's write paths (create story, submit canon event, request revision, etc.) need a real Postgres connection to do anything.

---

## P1 — Backend gaps (routes/logic that don't exist yet, not just untested)

5. **Cast-lock / family-tree endpoint.** The onboarding flow's "Lock cast" button currently just calls `POST /api/v1/stories` with a bare title — there's no real cast-roster or family-tree-summary endpoint. Design.md describes a richer cast-confirmation step this doesn't yet support.
6. **Progression-mode mutation endpoints.** `BranchControls`'s three buttons (Continue / Edit traits / Jump-rewind) have no backend endpoint to call — `services/progression.py`, `trait_states.py` exist as pure logic but nothing wires them to a `POST` route the frontend can hit.
7. **Job-dispatch submission route.** Nothing in the REST API actually calls `job_dispatcher.dispatch_pending` — canon-event requests and revision requests get created but never trigger a generation job.
8. **Idempotency-key / ETag semantics.** No mutating route implements the idempotent-replay or optimistic-concurrency behavior design.md calls for (only the DB-level idempotency key column exists).
9. **Report-listing endpoint.** `TraceDrawer` needs a known `run_id` because there's no `GET /generation-jobs/:id/agent-runs` to list them — needs a small new route.
10. **`quality_checks_job` resource** — `notebooks/03_operational_quality_checks.py` is written but not registered in `resources/jobs.yml`, so it can't actually run as a scheduled job yet.
11. **Real generation pipeline.** This is the big one: every agent (Director/World/Storyteller/Evaluator/Business) is currently a stub that returns fixed enum actions — there's no actual LLM call anywhere. `generation_job.py`/`report_job.py` raise `NotImplementedError` exactly at the point a real model adapter would go. This is the largest remaining scope item in the whole project and everything else (candidate generation, evaluator outcomes, chapter loop) is currently non-functional without it.

---

## P2 — Frontend wiring gaps ("every button" specifically)

12. **`WorkspaceStudio`'s three progression buttons are dead** (`web/app/page.tsx` lines ~47-53) — literally `<button>` with no `onClick`, left over from the original prototype-derived demo. The real, wired `BranchControls`/`ActivityFeed`/`TraitCard`/`useGenerationStream` components exist as standalone pieces but were never swapped in to replace this demo. This is the single most visible "button doesn't work" issue in the app today.
13. **No story/branch context provider.** `/world`, `/endings`, `/reports` currently take a raw UUID typed into a text box because nothing has ever listed the user's actual stories/branches for them to click through. Needs a stories-list view + branch picker.
14. **Revision form has no home.** `RevisionRequestForm` exists but no chapter-detail page renders it yet.
15. **Ending options, reports, ADR-201 perf targets** are all real but have never been exercised against live data — first real usage will surface bugs the unit tests can't catch (they mock the API layer).
16. **No Playwright run has ever happened.** Every e2e spec (`navigation`, `accessibility`, `onboarding`, `generation`, `recovery`) is written but unexecuted — this sandbox can't finish a Chromium download or run `--with-deps`. Needs to run once in a normal CI runner or your own machine.
17. **Archive/unarchive, blocked-generation retry, quota/policy-block UI** — none of these exist yet (Task 4H.4's remaining scope).

---

## P3 — Testing & verification still owed

18. Every DB-gated test (persistence, workers, security) needs one real run with `TEST_DATABASE_URL` set — they're currently only proven to *skip* correctly, not to *pass* against real data.
19. `tests/performance/*.js` (k6 scripts) have never run — no load has ever hit a live deployment.
20. Security suite covers RLS/personalization/redaction/injection/IP-disclosure, but explicitly does **not** cover: concurrent stale-write races, blocked safety categories (no content-moderation enum exists), sponsorship disclosure (no sponsorship concept exists), or quota-response copy (no quota system exists).
21. No secret/dependency scanner has run outside of what CI would do automatically (gitleaks job exists in `ci.yml` but hasn't executed on a real push since these changes).

---

## P4 — Security / ops / release gaps

22. **Observability isn't wired in.** `analytics/observability.py`'s `emit()`/`enforce_budget()` are tested library functions but nothing in `job_dispatcher.py`, the worker entry points, or any route actually calls them yet.
23. **No OpenTelemetry exporter** — logging uses the stdlib only.
24. **No per-user budget storage** — `enforce_budget` has no `budget_limit_usd` source to read from.
25. **Release checklist and rollback runbooks are written but unrehearsed** — no staging release or rollback has ever actually happened (Task 5.S1 sign-off is blocked on this).
26. **Deferred-scope items** already explicitly out of this release: image/comic export, animated portraits, multi-author collaboration, vector retrieval.

---

## Suggested order of attack

If the goal is "get one real user through one real story end-to-end," do these roughly in this order:

1. Deploy target + migrations live (P0.1-P0.2) — nothing else can be verified without this.
2. Swap `WorkspaceStudio`'s dead buttons for the real wired components (P2.12) — quick, high-visibility fix.
3. Add the progression-mutation + job-dispatch routes (P1.6-P1.7) so those buttons actually do something once wired.
4. Build a minimal story/branch list so `/world`, `/endings`, `/reports` aren't text-box-driven (P2.13).
5. Decide the real scope of the generation pipeline (P1.11) — this is the make-or-break item; everything upstream of it (candidate generation, evaluator, chapter loop) is currently a stub, and it's also the largest single piece of remaining work by far.
6. Run the DB-gated test suites for real (P3.18), then the e2e suite once on a normal machine (P2.16).
7. Wire observability into the actual pipeline (P4.22) once there's a real pipeline to observe.
8. Rehearse a staging deploy + rollback (P4.25) before calling anything production-ready.

Everything in P0-P2 is achievable without touching the model-integration question. P1.11 (a real generation pipeline) is a separate, much larger decision — it determines what LLM/provider you're using and how prompts are built, which nothing in this codebase currently specifies.
