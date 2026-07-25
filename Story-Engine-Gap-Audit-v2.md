# Story Engine — Gap Audit v2

**Scope:** re-audit of the current `design.md`, `task.md`, `requirements.md`, and the new `requirements-reconciliation.md`, cross-checked against each other and against the three original reference documents (`story-engine-requirements.md`, `story-engine-backend-design-final.md`, `StoryEngineProto.jsx`). This pass verifies every finding from the v1 audit and hunts specifically for anything new — including issues the v1 report only flagged as "recommend verifying" rather than actually checking line-by-line.

---

## Part A — Verification of the 13 v1 findings

All 13 are fixed. Evidence:

| # | v1 finding | Status | Where it's fixed |
|---|---|---|---|
| 1.1 | Blurred hidden-trait hint (genre-gated) | **Fixed** | `design.md` line 303 explicit supersession note; `requirements-reconciliation.md` row 1; `task.md` §0.4 row "Prototype hidden row" |
| 1.2 | Hard 20-character seed minimum | **Fixed** | `design.md` limits table (12-token clarification threshold, no minimum); `requirements.md` line 51 rewritten; `task.md` 4H.2 explicitly forbids porting the `>=20` gate |
| 1.3 | Direct kill/revive with no confirmation/evaluator step | **Fixed** | `task.md` 4H.4 explicit non-reuse instruction + pending/evaluating state requirement |
| 1.4 | No 3-mode progression composer in prototype | **Fixed (documented)** | `task.md` line 344 "Prototype boundary" note |
| 2.1 | Richer `story-engine-requirements.md` never reconciled (monetization, GR-5.2, GR-4.1, animated portraits, success metrics, quota numbers) | **Fixed** | New `requirements-reconciliation.md`; `design.md` lines 697/699/728; `task.md` 5I.1 product metrics |
| 2.2 | Relationship auto-suggestion on character introduction dropped | **Fixed** | `design.md` line 360; `task.md` 3E.4 |
| 3.1 | Configurable limits missing from table (choices, ending threshold, quotas) | **Fixed** | `design.md` limits table now has all four rows |
| 3.2 | Orphaned `genres` feature-gating schema note | **Fixed** | `design.md` line 582 explicit retirement note |
| 3.3 | No first-login user-provisioning task | **Fixed** | `task.md` 4G.2 JIT provisioning + idempotency test |
| 3.4 | No task owns prompt authoring/red-teaming | **Fixed** | `task.md` 3E.2 renamed, adds `prompts/`, red-team verification |
| 3.5 | No template licensing sign-off task | **Fixed** | New `task.md` Task 1B.4 |
| 3.6 | No LLM cost/spend guardrail | **Fixed (partially — see A2.5 below)** | `task.md` 5I.1 budget metrics + kill switch |
| 3.7 | No automated accessibility/contrast scan | **Fixed** | `task.md` 4H.1 adds axe-core + `accessibility.spec.ts` |

Part A confirms the previous round of edits was applied correctly and didn't just restate the problem — the fixes are concrete and traceable. Part B below is the new material for this version.

---

## Part B — New and residual issues found in this pass

### B1. [Critical] A real target-file collision now sits inside the plan the collision-checker task is supposed to catch

`resources/lakebase.yml` is declared as a target file in **both**:
- Task 1A.2 (Track A): *"Target Files: `databricks.yml`, `resources/variables.yml`, `resources/app.yml`, `resources/jobs.yml`, `resources/lakebase.yml`, `resources/permissions.yml`."*
- Task 1B.2 (Track B): *"Target Files: `resources/lakebase.yml`, `migrations/0001_bootstrap.sql`, `notebooks/01_lakebase_smoke_test.py`."*

Track A and Track B are declared parallel in the Build Order map (`Phase 1: Track A ─┐ ├─ Sync 1 / Track B ─┘`), and `task.md`'s own rule says *"Do not begin a task that edits another active track's target path."* This is a literal, same-phase, same-file collision between two concurrently-runnable tasks — exactly the failure mode the newly-added Task 1A.5 collision-checker exists to catch.

Worse, Task 1A.5's own verification line explicitly asserts the opposite of what's true: *"A fixture with a deliberately duplicated concurrent-track path fails CI; **the current task plan passes**..."* — it does not currently pass. If the checker is implemented as literally described, it will fail on day one against the plan's own content.

**Fix:** split ownership — have Task 1A.2 create only the bundle-resource skeleton (an empty/placeholder `resources/lakebase.yml` with no Lakebase-specific fields), and have Task 1B.2 be the sole owner of populating it, or rename so Task 1B.2 edits a distinct file (e.g. `resources/lakebase.instance.yml`) merged in by 1A.2 via bundle include. Either way, only one task should list `resources/lakebase.yml` as an owned target file.

### B2. [Medium] Track isolation preambles are stale relative to the tasks just added to them

- Track A's isolation line (`*Target isolation: repository root, resources/, .github/, and docs/adr/ only.*`) does not list `scripts/`, but the new Task 1A.5 targets `scripts/check_task_paths.py`.
- Track B's isolation line (`*Target isolation: notebooks/00_platform_setup.py, notebooks/01_lakebase_smoke_test.py, notebooks/02_audit_delta_smoke_test.py, and docs/runbooks/ only.*`) does not list `content/` or `docs/adr/`, but the new Task 1B.4 targets `content/templates/`, `content/template-manifest.csv`, and `docs/adr/003-template-rights.md`.
- Track I and Track J both declare `docs/adr/` in their isolation scope with no per-track filename prefix, which is ambiguous now that both tracks can plausibly add ADRs in the same phase.

**Fix:** update the three isolation preambles to match what their tasks actually touch, and consider giving each track a numbered ADR prefix (e.g., Track I owns `docs/adr/1xx-*`, Track J owns `docs/adr/2xx-*`) so the collision-checker being built in B1 has an unambiguous rule to enforce.

### B3. [Medium] The "insert yourself" self-avatar character was silently dropped, not deferred

`story-engine-backend-design-final.md`'s `entities` table has `is_user_avatar boolean | true for the "insert yourself" character`, and the prototype's World Sandbox copy says *"Insert yourself, introduce brand-new characters, shift the active realm..."* — this is a real, named feature in the prior design artifacts. It does not appear anywhere in the current `design.md` (data model, screens, or Deferred MVP Boundaries), nor in `task.md`, `requirements.md`, or `requirements-reconciliation.md`. Every other prototype/backend-design feature found in v1 got an explicit disposition (implemented, superseded, or deferred); this one has none — it simply isn't mentioned, which is different from a documented deferral.

**Fix:** add one line to `design.md`'s Deferred MVP Boundaries (or implement it if it's meant to ship) and one row to `requirements-reconciliation.md`, e.g.: *"User self-avatar / 'insert yourself' character: deferred; `entities.is_user_avatar` is not carried into the branch-scoped schema in MVP."*

### B4. [Medium] The prototype's live Comic Studio screen isn't named in the "do not reuse" list, even though it directly contradicts a stated requirement

`design.md`'s Progression & Volume Manager screen requires: *"In text MVP, comic/export controls are visibly marked 'Coming later' rather than appearing operable."* The prototype's Comic Studio (nav item "05 · Comic Studio," live panel regeneration, a working "Export PDF/PNG" button) is the opposite of that — a fully operable feature. Track H's "Prototype boundary" callout (`task.md` line 344) lists four specific behaviors not to port (hidden-trait row, 20-char gate, Sandbox mutations, two-choice reader) but never mentions the Comic Studio screen, even though it's an equally direct contradiction of the current spec.

**Fix:** add a fifth bullet to the Track H prototype-boundary note: *"Its Comic Studio screen (nav item 05) is fully operable in the prototype; the shipped Progression & Volume Manager must render comic/export controls as a non-operable 'Coming later' state instead."*

### B5. [Low] Two newly-added guardrails aren't in the central Configurable Product Limits table

This revision added real rules in prose but not in `design.md` §1's table, which is supposed to be the single source of truth for "guardrails must be configuration, not hard-coded":
- The trait-spiral "gentle nudge" (`design.md`'s Content Safety paragraph: *"Repeated requests that create a harmful trait spiral trigger a gentle in-context nudge..."*) has no defined repeat-count threshold anywhere.
- The per-user LLM cost/spend budget kill switch (`task.md` Task 5I.1) has no default budget number anywhere.

**Fix:** add two rows to the limits table, even as `TBD — confirm before Phase 5`, e.g. *"Regressive trait-edit nudge threshold"* and *"Per-user daily token/spend budget."*

### B6. [Low] The ending-readiness score has a threshold (0.75) but no defined formula

`design.md`'s limits table sets *"Automatic ending-readiness score: 0.75,"* but nowhere — not in the Ending Options screen spec, not in the Business/Evaluator agent descriptions — is it stated what inputs produce that 0–1 score (chapter count? business score? evaluator pacing note?). This is the same open question from the original requirements doc (§9, Q3: *"what's the system's heuristic for 'story has reached a plausible ending point'"*) — it now has a pass/fail number but the thing being measured is still unspecified, so 0.75 isn't independently checkable yet.

**Fix:** add one sentence to the Ending Options screen or business-agent description naming the actual inputs to the score (e.g., a weighted function of chapter count, business pacing sub-score, and open-thread count from Director memory).

### B7. [Low] Monetization/sponsorship disclosure has a data-model home but no screen-level UI spec

`requirements-reconciliation.md` states sponsorship metadata is *"supported in the template model,"* and `task.md` Task 2C.2 adds sponsorship/disclosure fields to the templates schema — but `design.md`'s actual screen specs (Story Seeding, Concept Selection, Template Library picker) still describe no sponsorship badge, "Presented by [Brand]" label, or weighted-suggestion disclosure copy anywhere. A front-end builder has a database column to read but no component spec telling them what to render with it.

**Fix:** add one line to the Story Seeding screen's "Components & interactions" bullet describing a disclosure badge/label wherever a sponsored or curated template/suggestion appears.

### B8. [Low, process] Accessibility/e2e suites only run at phase Sync Points, not per-PR

Task 1A.4's CI workflow runs "Python/TypeScript lint, type checks, unit tests, secret scan, and bundle validation" — it does not mention running the `tests/e2e/*` Playwright suite (including the new `accessibility.spec.ts` from Task 4H.1). Those only get exercised at Task 4.S1 (a Phase 4 sync point). For a document that is otherwise strict about CI gates, this means an accessibility regression could sit undetected for the whole of Phase 4 until the sync point runs.

**Fix:** either add a lightweight e2e/accessibility smoke subset to `ci.yml` per PR, or explicitly state in Task 1A.4 that e2e/accessibility suites are intentionally sync-point-gated rather than per-PR, so it's a decision instead of a gap.

---

## Summary table

| # | Finding | Severity | Status |
|---|---|---|---|
| B1 | `resources/lakebase.yml` collides across parallel Track A/B tasks; contradicts 1A.5's own verification claim | **Critical** | Open |
| B2 | Track A/B/I/J isolation preambles stale vs. their own new tasks | Medium | Open |
| B3 | Self-avatar "insert yourself" feature silently dropped, no deferral recorded | Medium | Open |
| B4 | Comic Studio screen not named in prototype "do not reuse" list | Medium | Open |
| B5 | Trait-spiral nudge and cost-budget thresholds missing from limits table | Low | Open |
| B6 | Ending-readiness score (0.75) has no defined scoring formula | Low | Open |
| B7 | Sponsorship disclosure has schema support but no screen UI spec | Low | Open |
| B8 | e2e/accessibility suite not wired into per-PR CI | Low | Open |

---

## Recommended next action

Fix B1 first — it's a real, mechanical defect in the plan (not a judgment call), it contradicts a claim the plan makes about itself, and it's a five-minute edit (rename or split ownership of one file across the two tasks). B2–B4 are quick documentation additions. B5–B8 are minor and can be batched into the same pass as B1–B4 without materially changing scope.
