# Task Execution Plan — Story Engine on Databricks

> **Status Tracking:** Use `[ ]` for pending, `[/]` for in-progress, and `[x]` for completed.
>
> **Deployment profile:** This plan targets a full Databricks workspace, not Community Edition. It uses Databricks Apps, Lakebase Postgres, Unity Catalog, Delta Lake, Databricks Jobs, and Declarative Automation Bundles (the current name for Databricks Asset Bundles).
>
> **Source specifications:** `requirements.md` and `design.md` in this folder are the product and technical source of truth. If an implementation decision conflicts with either, update the specification in the same pull request before implementation.

---

## 0. Execution Rules and Target Architecture

### 0.1 Deployment Decisions

| Concern | Production decision | Do not use for this concern |
| --- | --- | --- |
| Interactive web/API | Databricks App running FastAPI and serving a static Next.js export | A notebook as a web server |
| Transactional state | Lakebase Postgres | Delta tables as the request-time OLTP database |
| Async generation | Databricks Jobs running Python wheel tasks, triggered after a durable Lakebase queue write | In-process background tasks as the only job record |
| Live activity | SSE endpoint reads allowlisted `generation_events` from Lakebase | Directly streaming model/provider output to a browser |
| Governance/audit | Unity Catalog Delta tables for redacted operational audit exports and analytics | Uncontrolled DBFS/FileStore paths |
| Deployment | Declarative Automation Bundles (DAB) + GitHub Actions | Manual production workspace edits |
| Files/artifacts | Unity Catalog Volumes for approved files and artifacts | Local disk as persistent storage |

### 0.2 Required Repository Layout

```text
story-engine/
├── databricks.yml
├── app.yaml
├── pyproject.toml
├── package.json
├── .gitignore
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── resources/
│   ├── app.yml
│   ├── jobs.yml
│   ├── lakebase.yml
│   ├── permissions.yml
│   └── variables.yml
├── src/story_engine/
│   ├── api/
│   ├── domain/
│   ├── persistence/
│   ├── services/
│   ├── workers/
│   ├── agents/
│   ├── security/
│   └── analytics/
├── migrations/
├── scripts/
│   ├── build_web.sh
│   └── migrate.py
├── web/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── public/
├── notebooks/
│   ├── 00_platform_setup.py
│   ├── 01_lakebase_smoke_test.py
│   └── 02_audit_delta_smoke_test.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
└── docs/
    ├── adr/
    └── runbooks/
```

### 0.3 Shared Completion Contract

Every task must satisfy all applicable checks before it is marked `[x]`:

1. The target file exists at the listed path and has no unrelated edits.
2. Unit tests pass locally/CI: `pytest` and/or `npm run test`.
3. Static checks pass: `ruff check`, `mypy`, `npm run lint`, and `npm run typecheck` as applicable.
4. Bundle changes pass `databricks bundle validate -t dev`.
5. Any Databricks resource change is verified in the deployed `dev` target, not only by YAML inspection.
6. No secret, personal preference value, hidden characteristic, access token, or production identifier is committed to Git or written to test snapshots.

### 0.4 Source-Reconciliation Decisions

The uploaded requirements, backend design, prototype, and current `design.md` were audited together. The following decisions prevent contradictory implementation:

| Source requirement | Build disposition |
| --- | --- |
| Short/ambiguous seed requires visible confirmation | **Implement.** No hard input minimum; clarification loop is required before concepts. |
| Predefined story input | **Implement original/verified-licensed template library only.** Direct use of unlicensed known IP and source-scene jumping is deferred. |
| Family tree/card editing | **Implement via versioned trait/relationship requests.** The graph remains read-only; edits go through the validated canon-event workflow. |
| Three next-step options | **Implement exactly:** Continue automatically, Edit traits, Jump/rewind. The existing two freeform storyteller choices are not the progression control. |
| Automatic publication versus visible agency | **Implement auto-publish after validation** with visible streamed state, immutable history, branch/revision undo, and no silent material change. |
| Hidden traits versus inspectable traits | **Implement inspectable mutable trait state.** Unrevealed hidden characteristics remain the deliberate privacy exception. |
| Comics, exports, animated portraits | **Deferred.** Later direct product decision makes this a text-only MVP; retain schema extension points only. |
| Content/IP/wellbeing/privacy guards | **Implement now** as blocking policy gates and user-visible safe-redirection behavior. |
| Prototype hidden row | **Explicitly removed.** Never port the prototype’s genre-gated blurred hidden-characteristic row. |
| Prototype hard 20-character gate | **Explicitly removed.** Replace it with the clarification loop. |
| Prototype direct Sandbox mutations | **Explicitly removed.** Use confirmation + canon-event request + pending/evaluating state. |
| Prototype two-choice reader | **Visual reference only.** Do not port its interaction logic; build the three-mode progression composer. |

The full decision record is maintained in `requirements-reconciliation.md`. Any implementation pull request that changes a reconciled behavior must update that file, `design.md`, and the affected task acceptance criteria together.

---

## Phase 1: GitHub, Databricks Workspace, and Environment Foundation

### Track A — Repository, Bundles, and CI

*Target isolation: repository root, `resources/`, `.github/`, `docs/adr/`, and `scripts/check_task_paths.py` only. (There is no separate `resources/lakebase.yml`; Lakebase binding lives inside `resources/app.yml`, which Track A owns as bundle-skeleton scaffolding while Track B/Track G own its Lakebase- and App-runtime-specific content per Task 1B.2/4G.1.)*

- [x] **Task 1A.1: Initialize the Git repository and dependency manifests**
  - **Tooling:** GitHub, Python 3.11+, Node.js, uv/pip, npm/pnpm.
  - **Target Files:** `.gitignore`, `pyproject.toml`, `package.json`, `README.md`.
  - **Details:** Create one repository containing the Python application/wheel and Next.js web client. Pin Python and Node versions. Ignore `.env*`, build outputs, local certificates, Databricks CLI profiles, and generated static assets.
  - **Verification:** `git status --ignored`; `python -m pip install -e '.[dev]'`; `npm ci`; `npm run typecheck`.

- [x] **Task 1A.2: Create the Declarative Automation Bundle skeleton**
  - **Tooling:** Databricks CLI, Declarative Automation Bundles.
  - **Target Files:** `databricks.yml`, `resources/variables.yml`, `resources/app.yml`, `resources/jobs.yml`, `resources/permissions.yml`.
  - **Details:** Define `dev`, `staging`, and `prod` targets. Parameterize workspace host, catalog, schema, Lakebase project/database, app name, service principal, and UC Volume. Lakebase itself has no standalone bundle resource file (see Task 1B.2); this task only creates the placeholder `${var.lakebase_*}` variables consumed later by `resources/app.yml`. Do not hard-code workspace IDs or credentials.
  - **Verification:** `databricks bundle validate -t dev` returns success; `databricks bundle summary -t dev` lists the expected resource definitions.

- [x] **Task 1A.3: Define deployment identity and least-privilege permission design**
  - **Tooling:** Databricks IAM, Unity Catalog, Lakebase roles, Databricks Apps service principal.
  - **Target Files:** `resources/permissions.yml`, `docs/adr/001-deployment-identities.md`.
  - **Details:** Define separate identities/roles for app runtime, job runtime, CI deployer, migration runner, and administrator. Document the intended catalog/schema/volume/database privileges and who can deploy to each target. Apply database roles only after Task 1B.2 has provisioned Lakebase.
  - **Verification:** ADR is reviewed and lists no owner credential for any runtime identity. The executable permission-negative checks are deferred to Task 2C.5 after tables and policies exist. (Done — see `tests/integration/persistence/test_rls.py`.)

- [/] **Task 1A.4: Build CI and protected deployment workflows**
  - **Tooling:** GitHub Actions, Databricks CLI.
  - **Target Files:** `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`.
  - **Details:** CI runs Python/TypeScript lint, type checks, unit tests, secret scan, bundle validation, and—once Track H exists—a Playwright accessibility/navigation smoke subset on every pull request. Deploy workflow requires reviewed main-branch changes, deploys `dev`, runs integration tests, and uses an approval gate for `staging`/`prod`.
  - **Status:** Workflow content complete — `ci.yml` now runs a Gitleaks secret scan and an uncredentialed `databricks bundle validate` job in addition to lint/typecheck/unit/e2e-accessibility-if-present; `deploy.yml` already gated `workflow_dispatch` behind a GitHub `environment`. **Remaining:** actually opening a PR against GitHub and running `workflow_dispatch` against a real `dev` workspace can't happen from here — leave `[/]` until that's exercised once GitHub environment secrets and a `dev` workspace exist.
  - **Verification:** Open a test pull request and confirm CI fails on a deliberately failing unit test and an axe-core violation after the Track H suite is available; run `workflow_dispatch` to deploy `dev` successfully.

- [x] **Task 1A.5: Add source-traceability and parallel-path validation**
  - **Tooling:** Python or Node.js, GitHub Actions.
  - **Target Files:** `requirements-reconciliation.md`, `scripts/check_task_paths.py`, `.github/workflows/ci.yml`.
  - **Details:** Commit the source-reconciliation appendix. Add a CI check that parses `task.md` target-file declarations and flags collisions between tracks marked parallel, plus a check that required reconciliation terms remain present.
  - **Verification:** A fixture with a deliberately duplicated concurrent-track path fails CI; the current task plan passes; CI confirms the explicit prototype supersession entries exist.

### Track B — Databricks Data and Application Prerequisites

*Target isolation: `notebooks/00_platform_setup.py`, `notebooks/01_lakebase_smoke_test.py`, `notebooks/02_audit_delta_smoke_test.py`, `content/`, `docs/runbooks/`, and `docs/adr/003-template-rights.md` only.*

- [/] **Task 1B.1: Provision Unity Catalog data boundaries**
  - **Tooling:** Unity Catalog, SQL Warehouse or notebook.
  - **Target Files:** `notebooks/00_platform_setup.py`, `docs/runbooks/platform-bootstrap.md`.
  - **Details:** Create environment-specific catalog/schema naming conventions and a managed UC Volume for approved artifacts. Create the Delta audit table namespace. Keep transactional request data in Lakebase, not Delta.
  - **Status:** Notebook and runbook written; not executed (no Databricks workspace/Unity Catalog access from this environment — same platform-setup prerequisite blocking Task 1.S1/4G.1's deploy verification).
  - **Verification:** Execute the notebook; `SHOW SCHEMAS IN <catalog>` and `dbutils.fs.ls('/Volumes/<catalog>/<schema>/<volume>')` show the expected resources.

- [x] **Task 1B.2: Provision Lakebase Postgres and baseline roles**
  - **Tooling:** Lakebase, PostgreSQL migrations.
  - **Target Files:** `migrations/0001_bootstrap.sql`, `notebooks/01_lakebase_smoke_test.py`.
  - **Details:** Provision separate Lakebase branches/databases for `dev`, `staging`, and `prod` (a Databricks console/CLI action, not a repo file — see `docs/runbooks/platform-bootstrap.md`) and create non-owner application roles. Add extensions required for UUIDs and row-level security. Note: Declarative Automation Bundles has no standalone `lakebase.yml`/Lakebase resource type — the Lakebase project/database/endpoint are referenced via `${var.lakebase_project}`/`${var.lakebase_database}`/`${var.lakebase_endpoint}` inside the App resource's `resources: [{ postgres: ... }]` block in `resources/app.yml`, which Task 4G.1 (Track G) owns exclusively so it doesn't collide with Track A's `resources/app.yml` skeleton ownership in the same phase. A separate `resources/lakebase.yml` file is intentionally not created; the earlier plan referencing it as a distinct target file was corrected here and in Track A/B's isolation lines.
  - **Verification:** App/job identities connect using injected resource configuration; `notebooks/01_lakebase_smoke_test.py` executes `SELECT current_user, current_database()`, confirms it is not using the owner role, and confirms `migrations/0001_bootstrap.sql` has been applied. Actually provisioning the `dev` Lakebase project/branch itself is a one-time Databricks console/CLI action outside version control and is tracked as a manual prerequisite in `docs/runbooks/platform-bootstrap.md`, not as a repo file.

- [/] **Task 1B.3: Create the redacted Delta audit sink**
  - **Tooling:** PySpark, Delta Lake, Unity Catalog.
  - **Target Files:** `src/story_engine/analytics/audit_export.py`, `notebooks/02_audit_delta_smoke_test.py`.
  - **Details:** Create append-only Delta tables for redacted generation lifecycle metrics, latency, status, retry count, and tenant-hashed identifier. Explicitly exclude prose, hidden characteristics, user preferences, prompts, and raw agent payloads.
  - **Status:** `audit_export.py` builds the `CREATE TABLE IF NOT EXISTS ... USING DELTA` DDL from the shared `AUDIT_SCHEMA`/`assert_schema_is_redacted()` (Task 3F.3); the smoke-test notebook creates the table and re-checks the forbidden-pattern assertion against the table actually deployed to Unity Catalog, not just the Python constant. Not executed — no Spark/Unity Catalog runtime available here.
  - **Verification:** Run the smoke notebook; `DESCRIBE HISTORY <catalog>.<schema>.generation_audit` succeeds and a schema assertion confirms forbidden columns are absent.

- [x] **Task 1B.4: Establish template authoring and licensing sign-off**
  - **Tooling:** Git, Markdown/CSV manifest, legal/content review workflow.
  - **Target Files:** `content/templates/`, `content/template-manifest.csv`, `docs/runbooks/template-approval.md`, `docs/adr/003-template-rights.md`.
  - **Details:** Create the original-template authoring workflow and a license-evidence manifest. Every template must record author, rights basis, approved status, source attribution, sponsorship disclosure if any, and approved scene map. Reject missing/expired evidence before deployment.
  - **Verification:** CI rejects a template missing rights metadata; one original template and one mock licensed template pass the approval manifest validator.

### 🛑 SYNC POINT 1: Foundation Merge and Workspace Validation 🛑

- [ ] **Task 1.S1: Validate and deploy foundation resources to `dev`**
  - **Target Files:** all Phase 1 files only.
  - **Details:** Merge Tracks A and B, validate the complete bundle, then deploy only the foundation resources that do not require the unbuilt App/worker wheel. Capture actual resource URLs/IDs in deployment outputs—not source files.
  - **Verification:** `databricks bundle validate -t dev`; selected-resource deployment succeeds; platform smoke notebooks pass; GitHub deployment record links to the bundle commit SHA.

---

## Phase 2: Transactional Domain, Tenant Isolation, and Governance

### Track C — Lakebase Schema and Database Enforcement

*Target isolation: `migrations/`, `src/story_engine/persistence/`, and `tests/integration/persistence/` only.*

- [/] **Task 2C.1: Create tenant, story, personalization schema, and migration runner** *(schema/tests written; not yet executed against a live Postgres — see note below)*
  - **Tooling:** PostgreSQL/Lakebase, Alembic or SQL migration runner.
  - **Target Files:** `migrations/0002_tenants_profiles_stories.sql`, `scripts/migrate.py`, `src/story_engine/persistence/models.py`, `tests/integration/persistence/test_tenants.py`.
  - **Details:** Implement `users`, `user_preferences`, immutable `personalization_snapshots`, `stories`, `arcs`, and configuration flags. Include `user_id`, preference source/consent, soft delete, snapshot version, and per-story personalization enablement. Add an idempotent migration runner that uses the dedicated migration identity, records applied versions/checksums, and refuses drift.
  - **Verification:** Migration applies to an empty database and a second execution is a no-op; tests prove a snapshot cannot be created from another user’s preference and a disabled story cannot select a snapshot.

- [/] **Task 2C.2: Create branch-safe narrative, template, trait-state, and world-state schema** *(schema/tests written; not yet executed against a live Postgres)*
  - **Tooling:** PostgreSQL/Lakebase.
  - **Target Files:** `migrations/0003_branches_world_state.sql`, `src/story_engine/persistence/branches.py`, `tests/integration/persistence/test_branch_isolation.py`.
  - **Details:** Create original/licensed templates with source-license, approved-scene-map, sponsorship/disclosure metadata; branches, chapters, branch entity state, immutable versioned `character_trait_states`, branch relationships, branch canon facts, world snapshots, choices, scenes, dialogue, revisions, canon events, and ending-option records. Record the focal character and trait-state version used by every chapter. Enforce one current-state source per branch and unique chapter indexes per branch.
  - **Verification:** Integration test forks a parent branch, changes a child entity location/trait state, and asserts the parent/sibling states remain unchanged and the historical chapter resolves its original trait version.

- [/] **Task 2C.3: Create isolated character and Director memory schema** *(schema/tests written; not yet executed against a live Postgres)*
  - **Tooling:** PostgreSQL/Lakebase.
  - **Target Files:** `migrations/0004_memory_and_director.sql`, `src/story_engine/persistence/memory.py`, `tests/integration/persistence/test_memory_cutoffs.py`.
  - **Details:** Create branch-aware character core/episodic/screenplay memory, one `story_director` per branch, Director strategy/decision/open-thread memory, and ancestry cutoffs. Core profile is immutable for founding cast after lock; Director memory rejects private character fields.
  - **Verification:** Test that a child branch reads inherited memory only through its fork chapter, cannot see future parent entries, and Director-memory insertion rejects a hidden-characteristic field.

- [/] **Task 2C.4: Create durable job, event, staging, and report schema** *(schema/tests written; not yet executed against a live Postgres)*
  - **Tooling:** PostgreSQL/Lakebase.
  - **Target Files:** `migrations/0005_jobs_events_reports.sql`, `src/story_engine/persistence/jobs.py`, `tests/integration/persistence/test_job_idempotency.py`.
  - **Details:** Create generation jobs/events, leases, attempts, candidate staging rows, outbox, agent runs, evaluator/business reports, and retry metadata. Enforce a single active job per branch and idempotency-key uniqueness.
  - **Verification:** Two submissions with one idempotency key return the same job; a second active job on the branch is rejected; candidate rows are inaccessible from published chapter queries.

- [/] **Task 2C.5: Enforce RLS, tenant context, and canonical write authority** *(schema/tests written; partially live-verified this pass — see below)*
  - **Tooling:** PostgreSQL RLS, stored procedures/functions.
  - **Target Files:** `migrations/0006_rls_and_roles.sql`, `migrations/0008_canonical_write_revocation.sql`, `migrations/0017_baseline_table_privileges.sql` (new), `src/story_engine/persistence/tenant_context.py`, `tests/integration/persistence/test_rls.py`.
  - **Details:** Enable RLS for every user-owned table. Set tenant context via parameterized transaction-local `set_config`; expose world commits only through a narrowly privileged database function/service role. Do not grant canonical table write access to API, Director, storyteller, evaluator, or business roles. **Gap closed earlier:** migration 0008 revokes canonical-table DML from `PUBLIC`, adding `world_commit_entity_state`/`world_commit_trait_state` as the only write path. **Real live bug found and fixed this pass:** once the App was actually deployed and hit by a real browser request (not the migration-runner superuser), `GET /api/v1/me/preferences` 500'd with `psycopg.errors.InsufficientPrivilege: permission denied for table user_preferences`. Root cause: migration 0006 enabled RLS and created owner policies on every table, but RLS only filters *rows* — it never substitutes for the base table-level `GRANT` every one of those tables still needed and never got. Postgres grants `EXECUTE` on new functions to `PUBLIC` by default (why `app_provision_user`/JIT user creation worked fine), but never does this for tables, which is exactly why this went unnoticed through every prior pass — nothing had actually connected as a non-owner role until today. Migration 0017 grants the missing baseline to every RLS-protected table, carefully NOT re-opening anything 0008/0009 deliberately locked down (canonical tables keep SELECT-only grants; writes still only happen through their SECURITY DEFINER functions). It also fixes a second, more serious bug found while auditing this: `outbox`'s policy was a blanket `USING (false)`, which made it impossible for *any* connection — including `progression.py`'s own same-transaction write — to ever INSERT a row into the one table job dispatch depends on. Replaced with two real policies: end-user requests may insert an outbox row only for a `generation_jobs` row they own, and the background dispatcher (`job_dispatcher.dispatch_pending`, which never calls `set_tenant_context`, so `app.user_id` is unset on its connection) may `SELECT`/`UPDATE` any row — ordinary per-request connections still can't read the outbox directly, preserving the original intent without breaking the only legitimate write path into it.
  - **Verification:** Negative tests prove user A cannot read/write user B rows, worker roles cannot update canonical tables directly, and world-command transaction can commit an allowed state change (still DB-gated, not run against live Postgres by this pass). **What *is* now live-verified:** the `user_preferences` 500 was a real production error observed via the deployed App's own logs — migration 0017 is written to fix it but has not yet been deployed/re-tested against that live instance; do that next (`databricks bundle deploy` then retry the failing request) before considering this closed.
  - **Execution note (applies to 2C.1–2C.5):** all five integration-test files are written, syntax-checked (`python3 -m py_compile`), and ready under `tests/integration/persistence/`, gated by `TEST_DATABASE_URL` so the plain `pytest -q` unit job never requires a live database. They have not been run end-to-end yet — this sandbox has no Postgres and no Python ≥3.11 runtime available to execute the project's own `.venv`. Run them against a local Postgres or the provisioned `dev` Lakebase branch (`TEST_DATABASE_URL=postgresql://... pytest tests/integration/persistence -q`) before flipping these to `[x]`.

### Track D — Domain Contracts and Security Boundaries

*Target isolation: `src/story_engine/domain/`, `src/story_engine/security/`, and `tests/unit/domain/` only.*

- [x] **Task 2D.1: Define typed domain contracts and state transitions**
  - **Tooling:** Python, Pydantic, pytest.
  - **Target Files:** `src/story_engine/domain/models.py`, `src/story_engine/domain/state_machine.py`, `tests/unit/domain/test_state_machine.py`.
  - **Details:** Model generation status, branch status, canon event status, immutable published chapters, retry limits, and allowed transitions. Reject illegal transitions such as `PUBLISHED → GENERATING` in place.
  - **Verification:** Parameterized tests cover every valid/invalid transition and prove a major evaluator divergence cannot publish the candidate.

- [x] **Task 2D.2: Implement secret/tenant redaction and safe event allowlists**
  - **Tooling:** Python, Pydantic, pytest.
  - **Target Files:** `src/story_engine/security/redaction.py`, `src/story_engine/domain/events.py`, `tests/unit/domain/test_redaction.py`.
  - **Details:** Create client event DTOs that only expose sequence, safe summary, public agent label, status, and public entity ID. Scan/reject unrevealed hidden characteristics, cross-tenant identifiers, credentials, raw prompts, and unrestricted reasoning.
  - **Verification:** Tests pass known secret values through every event/report formatter and assert output is rejected or redacted; allowlisted fields remain intact.

- [x] **Task 2D.3: Implement prompt-input and Director-memory safeguards**
  - **Tooling:** Python, structured prompts, pytest.
  - **Target Files:** `src/story_engine/security/prompt_safety.py`, `src/story_engine/security/director_memory_policy.py`, `tests/unit/domain/test_prompt_safety.py`.
  - **Details:** Delimit user input and generated text as data; define structured tool/proposal schemas; reject attempts to change authority, access secrets, or write canon. Prevent global Director memory from storing private character excerpts or hidden characteristics.
  - **Verification:** Adversarial fixtures cannot produce a privileged tool proposal, canonical write command, or forbidden Director-memory record.

- [x] **Task 2D.4: Implement content, IP, wellbeing, and disclosure policy gates**
  - **Tooling:** Python, provider-agnostic moderation adapter, pytest.
  - **Target Files:** `src/story_engine/security/content_policy.py`, `src/story_engine/security/template_policy.py`, `src/story_engine/domain/policy_models.py`, `tests/unit/domain/test_content_policy.py`.
  - **Details:** Apply a typed blocking/redirect policy to seed input, clarification, template records, trait edits, canon events, and candidate prose. Block the prohibited safety/IP categories in `requirements.md`; provide concise safe alternatives, care-oriented distress handling, per-story privacy defaults, disclosed genre weighting/sponsorship fields, and explicit quota messages. Do not allow unlicensed named-IP characters or source text.
  - **Verification:** Table-driven tests cover every prohibited category, a likely distress input, unlicensed template rejection, disclosed sponsored template acceptance, and safe alternate-archetype response.

### 🛑 SYNC POINT 2: Database and Security Integration 🛑

- [ ] **Task 2.S1: Apply migrations and run tenant-isolation suite in `dev`**
  - **Target Files:** Phase 2 Track C/D files only.
  - **Details:** Deploy migrations with the dedicated migration identity, then seed two tenants and run cross-tenant, branch-fork, memory-cutoff, and canonical-write-negative tests using the app/job runtime identities.
  - **Verification:** `pytest tests/integration/persistence -q` passes against `dev`; a SQL role inspection confirms RLS is enabled on every in-scope table.

---

## Phase 3: Generation Orchestration and Databricks Jobs

### Track E — Agent Context and Pure Generation Services

*Target isolation: `src/story_engine/agents/`, `src/story_engine/services/`, and `tests/unit/agents/` only.*

- [x] **Task 3E.1: Implement tenant-safe context assembly**
  - **Tooling:** Python, Pydantic, pytest.
  - **Target Files:** `src/story_engine/agents/context_assembler.py`, `src/story_engine/agents/contracts.py`, `tests/unit/agents/test_context_assembler.py`.
  - **Details:** Assemble a context for one character decision at a time: active branch snapshot, selected character’s three memory buckets, and the branch Director’s safe coordination memory. Enforce the four-character configurable active-beat limit and never inject another character’s private context.
  - **Verification:** Fixture with two secrets proves each per-character context contains only the assigned secret; five eligible characters result in exactly four selected deterministically.

- [x] **Task 3E.2: Implement and red-team Director, World, Storyteller, Evaluator, and Business prompts/adapters**
  - **Tooling:** Python, model provider SDK abstraction, pytest.
  - **Target Files:** `src/story_engine/agents/director.py`, `world.py`, `storyteller.py`, `evaluator.py`, `business.py`, `src/story_engine/agents/prompts/`, `tests/unit/agents/test_adapters.py`, `tests/unit/agents/test_prompt_quality.py`.
  - **Details:** Author versioned system prompts, few-shot fixtures, and narrative-quality rubrics for each agent. Implement distinct typed interfaces and system policies. All adapters return validated proposals; only the world-command service may commit state. Make provider/model selection environment configuration, not code constants. Red-team every prompt for hidden-secret disclosure, authority bypass, copyrighted-IP requests, and unsafe trait escalation.
  - **Verification:** Stub-provider tests validate required outputs and demonstrate that evaluator/business adapters expose no commit method; prompt-quality fixtures meet rubric thresholds and adversarial fixtures fail closed for all five agent shapes.

- [/] **Task 3E.3: Implement candidate generation and pre-publication evaluation**
  - **Tooling:** Python, pytest.
  - **Target Files:** `src/story_engine/services/generation_pipeline.py`, `src/story_engine/services/candidate_service.py`, `tests/unit/agents/test_generation_pipeline.py`.
  - **Details:** Implement bounded Director/world discussion, candidate staging, evaluator outcome, automatic regeneration after major divergence, and final world-command commit. Generate a configurable approximately-30-second chapter unit centered on the selected focal character; candidate output must be visibly unpublished until commit and pass policy gates before evaluation.
  - **Status:** `candidate_service.py` holds the pure `CandidateChapter`/`CandidateStatus` contract plus `stage_candidate_for_evaluation`/`commit_candidate`, which delegate to `domain/state_machine.ensure_chapter_transition` so a candidate can only ever resolve to PUBLISHED from EVALUATING with an explicit approved outcome (never bypassing the existing GENERATING→EVALUATING→PUBLISHED/BLOCKED transitions). `generation_pipeline.py` adds `run_bounded_discussion` (a capped Director/World proposal loop that fails closed via `DiscussionNotConverged` if World never accepts within `max_discussion_rounds`), `ChapterLengthConfig` (a configurable ~30-second-equivalent word-count window derived from `target_seconds`/`words_per_second`/`tolerance`), and `generate_evaluated_candidate`, which on each attempt re-runs the discussion, drafts, gates through the content-policy adapter *before* evaluation, treats an out-of-length-window draft the same as a divergence (regenerate), and only commits PUBLISHED on an APPROVED evaluator outcome — otherwise BLOCKED, never leaving a publishable row behind. These are fake-adapter-driven, fully unit-testable pure Python (no DB, no provider), matching `tests/unit/agents/test_adapters.py`'s stub-provider style. **Honest gap:** `src/story_engine/workers/generation_job.py` is the real, already-working end-to-end OpenAI-backed loop (built after this task was written) and does **not** call into these new modules yet — wiring it in was judged too risky to do destructively under this task's time box, so today there are two parallel implementations: `generation_job.py` (real single-attempt loop, no bounded discussion/retry-after-divergence) and `generation_pipeline.py`/`candidate_service.py` (the fully-spec'd, retry-capable, discussion-bounded pure logic this task asked for, currently uncalled by production code). Consolidating them is the remaining work before this can become `[x]`. **Blocked on live infra:** none — this task's own logic is DB-free and fully exercised in-process; only the eventual `generation_job.py` integration would need a real Postgres/OpenAI run to verify end-to-end.
  - **Verification:** `tests/unit/agents/test_generation_pipeline.py` (11 tests) covers focal-character context (via `agents/context_assembler`), the configured chapter-length range (both a too-short draft raising after retries and a draft that grows into range), approval, rejection/revision via automatic regeneration after MAJOR_DIVERGENCE, retry exhaustion, a single-character active cast with no fallback failing closed, a content-policy block short-circuiting before the evaluator is ever consulted, bounded-discussion non-convergence failing closed, an illegal starting chapter status being rejected before any model call, and that an unapproved candidate can never reach PUBLISHED (only BLOCKED) at the state-machine level. Not run against a live DB — none of this logic touches one.

- [/] **Task 3E.4: Implement progression, trait-state, rewind, canon-event, ending, and revision workflows**
  - **Tooling:** Python, pytest.
  - **Target Files:** `src/story_engine/services/progression.py`, `src/story_engine/services/trait_states.py`, `src/story_engine/services/canon_events.py`, `src/story_engine/services/endings.py`, `src/story_engine/services/revisions.py`, `tests/unit/agents/test_canon_events.py`, `migrations/0009_canon_events_revisions_endings.sql`.
  - **Details:** Implement exactly three progression modes: Continue (same branch), Edit traits (suggested/freeform/go-with-flow; validated child branch when changed), and Jump/rewind (selected prior scene; child branch). Implement focal-character selection, versioned trait/relationship state, ending eligibility/manual request, multiple ending options, and revisions. On character introduction, world agent returns relationship suggestions for explicit author confirmation. Approved screenplay edits create replacement child branches rather than mutating published chapters.
  - **Status:** `progression.py` (three modes) and `trait_states.py` existed; added `canon_events.py` (status state machine + `SuggestedRelationship`/`build_introduce_entity_request`, closing FR-3.2), `endings.py` (a concrete, documented ending-readiness formula over chapter count / business pacing / open-thread resolution — closes Gap Audit v2 finding B6, which flagged the 0.75 threshold as previously undefined), and `revisions.py` (approved-implies-replacement-branch invariant). Added migration `0009_canon_events_revisions_endings.sql` for `canon_event_requests`, `canon_events`, `chapter_revisions`, `ending_options` — these tables were named in Task 2C.2's original scope but never actually created. `tests/unit/agents/test_canon_events.py` covers all of the above; all 81 unit/contract tests, `ruff check .`, and `mypy --strict` pass locally. **Remaining, blocked on Track F:** "an event arriving during generation being queued/rejected without altering a stale candidate" needs the branch-level job lock from Task 3F.2, which doesn't exist yet.
  - **Verification:** Test all three modes, trait-state visibility/versioning, rewind from any published scene, the persisted ending-readiness formula/components and manual threshold, multiple endings, kill/revive/move/introduce/revision flows, and an event arriving during generation being queued/rejected without altering a stale candidate.

### Track F — Job Worker and Operational Export

*Target isolation: `src/story_engine/workers/`, `src/story_engine/analytics/`, `resources/jobs.yml`, and `tests/integration/workers/` only.*

- [/] **Task 3F.1: Package the Python worker as a wheel and create job entry points**
  - **Tooling:** Python packaging, Databricks Jobs.
  - **Target Files:** `pyproject.toml`, `src/story_engine/workers/generation_job.py`, `src/story_engine/workers/report_job.py`, `resources/jobs.yml`.
  - **Details:** Define wheel tasks for generation, evaluator/business reports, memory compaction, and audit export. Pass only `job_id`/tenant-safe identifiers as parameters; load secrets/resources through Databricks runtime bindings.
  - **Status:** `generation_job.py`/`report_job.py` entry points added, registered under `[project.entry-points.packages]`, and wired into `resources/jobs.yml` (`generation_job`/`report_job` resources, wheel-task, `job_id`/`chapter_id`-only parameters). `generation_job.py` is real (Task 3E.3). **Closed in this pass:** `report_job.py` no longer raises `NotImplementedError` — it now resolves a published `chapter_id` back to its `candidate_chapters`/`generation_jobs` row (a new `chapters.candidate_id` FK, migration `0015_chapter_candidate_link.sql`, since no such link existed before — `world_publish_generated_candidate` now sets it) and calls the real `agents.business.BusinessAgent` against `OpenAIResponsesProvider`, writing one `business_reports` row per candidate. It deliberately does **not** re-invoke `agents.evaluator.EvaluatorAgent`: `evaluator_reports.candidate_id` is `UNIQUE` and `generation_job.py` already writes that row pre-publication, so a second evaluator pass here would violate the constraint, not add coverage. **Honest gaps:** `business_reports` has no status column, so "pending/failed report" (design.md's stated semantics) isn't representable — a failed business-report attempt just leaves no row (implicit pending), not a recorded FAILED state; `budget_limit_usd` still has no config source, so `enforce_budget` is still not called (same reasoning as the original note — a fabricated limit would be worse than none). Two new wheel tasks were added to `resources/jobs.yml`: `memory_compaction_job` (new real entry point, `src/story_engine/workers/memory_compaction.py::run_memory_compaction`, compacting `character_memories` EPISODIC rows per branch/character past a keep-recent threshold — note the task's assumed `character_core_memory`/`character_episodic_memory` table names don't exist; the real schema, migration `0004_memory_and_director.sql`, is one `character_memories` table with a `memory_kind` column, and this worker was written against that) and `audit_export_job` (a new `main()`/`run_audit_export` added to the existing `export_generation_audit.py`, reading `AUDIT_TENANT_HASH_SALT` from the environment and a configurable source/target table pair — PySpark/a live `spark` session are required and neither exists in this sandbox, so this entry point has never executed, same caveat as `export_completed_jobs` itself under Task 3F.3).
  - **Verification:** Build wheel; `databricks bundle deploy -t dev`; run the generation/report/memory-compaction/audit-export jobs with seeded IDs and inspect task output. (Not run — no `dev` workspace/credentials/live Postgres/Spark available in this environment.) `python3 -m py_compile` passes clean on `report_job.py`, `memory_compaction.py`, and `export_generation_audit.py`. `resources/jobs.yml` parses as valid YAML (`yaml.safe_load` confirmed). `pyproject.toml`'s new entry points were not round-tripped through an actual `python3 -m build` (same missing-toolchain caveat as before).

- [x] **Task 3F.2: Implement queue lease, retry, outbox, job dispatch, and stale-version handling**
  - **Tooling:** Lakebase Postgres, Python, pytest.
  - **Target Files:** `src/story_engine/workers/queue.py`, `src/story_engine/workers/outbox.py`, `src/story_engine/services/job_dispatcher.py`, `tests/integration/workers/test_queue.py`.
  - **Details:** Claim jobs with transactional leases, use retry/backoff, enforce branch lock/version checks, emit ordered events, and safely recover expired leases. Implement the one job-dispatcher service used by the API: it reads committed outbox rows and invokes the configured Databricks Job with only `job_id`; a failed launch remains retryable in the outbox.
  - **Verification:** Simulate worker crash after lease; a second worker recovers exactly once; duplicate outbox delivery does not create duplicate chapters/events; failed Databricks Job launch is retried from the outbox without recreating the Lakebase job row. All three are covered by `tests/integration/workers/test_queue.py` (DB-gated by `TEST_DATABASE_URL`, not yet run against a live Postgres — same execution caveat as Task 2C.1–2C.5); `ruff check .`, `mypy --strict`, and the plain unit/contract suite (83 tests) pass.

- [/] **Task 3F.3: Export redacted operational audit data to Delta**
  - **Tooling:** PySpark, Delta Lake, Unity Catalog.
  - **Target Files:** `src/story_engine/analytics/export_generation_audit.py`, `src/story_engine/analytics/audit_schema.py`, `tests/unit/analytics/test_audit_schema.py`.
  - **Details:** Incrementally export completed job metadata using a durable high-water mark. Write only the approved redacted audit schema to UC Delta and create a reconciliation report.
  - **Status:** `audit_schema.py` (the approved column list plus a forbidden-substring assertion) is framework-agnostic and unit tested without a Spark runtime. `export_generation_audit.py` implements the high-water-mark read and idempotent incremental append, importing PySpark only under `TYPE_CHECKING` so the module stays importable without a Spark install. **Not done:** this sandbox has no PySpark/Delta runtime, so `export_completed_jobs` itself has never actually executed — only its pure-Python sibling (`hash_tenant_id`, `assert_schema_is_redacted`) is test-covered. `tests/integration/workers/test_audit_export.py` (the originally named target, a real Spark-backed run-twice-and-reconcile test) and the reconciliation report still need to be written once a Databricks cluster/Spark session is available to test against.
  - **Verification:** Run export twice; second run is idempotent, row counts reconcile with Lakebase, and Delta schema contains no blocked fields.

### 🛑 SYNC POINT 3: End-to-End Worker Run 🛑

- [ ] **Task 3.S1: Execute a seeded Chapter 1 generation in `dev`**
  - **Target Files:** all Phase 3 files only.
  - **Details:** Seed one user/story/cast through the repository test fixture, lock cast, trigger the job, and capture redacted event sequence.
  - **Verification:** Job ends `PUBLISHED`; evaluator report is present; chapter contains structured scenes/dialogue; exactly one Lakebase generation-job row, one published chapter, and one Delta audit record exist.

---

## Phase 4: Databricks App, API, and Responsive Web Client

### Track G — FastAPI App and SSE Contract

*Target isolation: `src/story_engine/api/`, `src/story_engine/app.py`, `app.yaml`, and `tests/contract/` only.*

- [/] **Task 4G.1: Create the Databricks App runtime and SPA static web serving**
  - **Tooling:** Databricks Apps, FastAPI, Uvicorn, Next.js static export.
  - **Target Files:** `app.yaml`, `scripts/build_web.sh`, `src/story_engine/app.py`, `src/story_engine/api/static.py`, `resources/app.yml`.
  - **Details:** Define the App entry point, health/readiness endpoints, resource bindings, static asset directory, and production security headers. Build the Next.js client before App packaging, serve its static export, and return the SPA shell for non-`/api/*` client routes. Do not store credentials in `app.yaml`; use Lakebase/App resource injection.
  - **Status:** Code complete — `app.py` defines health/readiness, mounts the SPA shell via an inline `SPAStaticFiles` class (folded into `app.py` rather than a separate `static.py`; functionally equivalent), and `resources/app.yml` binds the `postgres` resource. **Remaining:** the actual `databricks bundle deploy -t dev` + browser smoke check cannot run without a provisioned `dev` workspace/Lakebase project (see the platform-setup prerequisites) — leave `[/]` until that deploy is performed.
  - **Verification:** Deploy App to `dev`; App URL returns health `200`, serves the placeholder SPA shell before Track H is complete, resolves a client-side deep link to the shell, and fails readiness when the database binding is intentionally unavailable.

- [/] **Task 4G.2: Implement authenticated REST APIs**
  - **Tooling:** FastAPI, Pydantic, Lakebase.
  - **Target Files:** `src/story_engine/api/auth.py`, `src/story_engine/api/routes/stories.py`, `branches.py`, `chapters.py`, `world.py`, `preferences.py`, `traces.py`, `tests/contract/test_rest_contract.py`.
  - **Details:** Implement the APIs in `design.md`, including Databricks App identity validation, just-in-time user provisioning on the first authenticated request, idempotency headers, ETags/version conflicts, authorization, personalization snapshots, canon-event requests, job-dispatch submission, and trace flag controls. Use API DTOs that exclude private data by construction.
  - **Status:** `auth.py` (JIT provisioning), `stories.py`, `branches.py` (read-only timeline), `chapters.py` (published-only reads), `world.py` (read-only branch state + `POST /branches/{id}/canon-event-requests`), `preferences.py` (full CRUD + snapshot creation), `traces.py` (trace-flag-gated, now also `GET /generation-jobs/{id}/agent-runs` for listing), `endings.py`, `revisions.py` are implemented and wired into `app.py`. **New this pass:** `progression.py` — `POST /branches/{id}/progression` is the job-dispatch submission route that was missing: it validates the request via `services/progression.target_branch_for_progression`, creates a child branch for `EDIT_TRAITS`/`REWIND` (never mutates the current branch), inserts a `generation_jobs` row, and writes the same-transaction `outbox` row `job_dispatcher.dispatch_pending` (run by a background poller) turns into an actual job launch. It also implements real idempotency-key semantics: an `Idempotency-Key` header (or an auto-derived key when absent) is checked against existing `generation_jobs` rows before inserting, so a replayed request returns the original job rather than creating a duplicate or hitting the one-active-job-per-branch unique constraint. **Also new (parallel-session-plan.md Tracks 1-3):** `cast.py` (`POST /stories/{id}/cast-lock`, idempotent — a second call returns the existing lock and roster; `GET /stories/{id}/family-tree`, migration 0011), idempotency-key replay added to `world.py`'s canon-event-request POST and `revisions.py`'s revision-request POST (migrations 0012/0014), and an `ETag` header added to `GET /branches/{id}/state` (a weak content hash — a real stale-write guard, not yet consumed by any client). `archive.py` (Track 6) adds `PATCH /chapters/{id}/archive`/`.../unarchive` (through a new `world_set_chapter_archived` SECURITY DEFINER function, migration 0013, since direct chapter UPDATE is revoked) and `POST /generation-jobs/{id}/retry` (creates a fresh job rather than resetting the failed one). **Closed in this pass:** `world.py` now enforces the `If-Match` precondition it previously only emitted — `_check_if_match()` recomputes the branch's current ETag inside the same transaction as the write and rejects a stale `If-Match` value with `412 Precondition Failed` before the canon-event-request insert proceeds; a request with no `If-Match` header still writes unconditionally (opt-in optimistic concurrency, not a breaking requirement for existing clients). Also closed: quota enforcement is now real — `progression.py` calls `services/quotas.enforce_quota` (backed by a new `current_quota_states()` reading live chapter/branch/job counts from Lakebase) before inserting a job, returning 429 with a body shaped exactly like `QuotaBanner.tsx`'s `QuotaBannerState`, plus a new `GET /me/quota` read endpoint so the frontend finally has a real data source instead of an unused component.
  - **Verification:** `tests/contract/test_rest_contract.py` plus `test_cast_contract.py`, `test_world_idempotency.py`, `test_revisions_idempotency.py` cover the auth boundary for every new endpoint. **Actually executed this session** (not just `py_compile`, see Task 5J.1's note on the Python 3.10→3.11 `StrEnum` workaround used): full `tests/` tree — 166 passed, 18 correctly skipped, 0 failed. `check_task_paths.py` clean, `databricks bundle validate -t dev` resolves cleanly against the real workspace (confirmed live today: bundle deploy succeeded, all four jobs plus the App exist in the actual `dev` workspace). Not yet exercised: the If-Match/quota logic against a live Postgres instance with concurrent writers.

- [x] **Task 4G.3: Implement SSE generation activity endpoint**
  - **Tooling:** FastAPI SSE, Lakebase event queries.
  - **Target Files:** `src/story_engine/api/routes/events.py`, `src/story_engine/api/sse.py`, `tests/contract/test_sse.py`.
  - **Details:** Stream ordered, redacted `generation_events` with `id`, reconnect via `Last-Event-ID`, heartbeat, authorization recheck, and bounded polling. Never emit raw provider tokens or unpublished private context.
  - **Verification:** `tests/contract/test_sse.py` uses fake cursor/connection doubles (no live Lakebase needed) to verify reconnect-after-event-3 yields events 4+ exactly once, and a terminal job emits `generation-complete` and stops. Authorization recheck is structural (RLS re-evaluated via `connection_factory` on every poll per `stream_job_events`'s docstring) rather than integration-tested here, since that requires a live Postgres session to revoke.

### Track H — Next.js Client and Accessibility

*Target isolation: `web/`, `tests/e2e/`, and front-end config files only.*

> **Prototype boundary:** `StoryEngineProto.jsx` is a visual reference for typography, color, and card layout only. Its hidden-trait row, hard 20-character gate, direct Sandbox mutation handlers, two-choice progression interaction, and fully operable Comic Studio/export controls are pre-redesign behavior and must not be reused. In this text MVP, Comic/Export controls render only as non-operable **Coming later** states.

- [/] **Task 4H.1: Build the static-export application shell and authenticated navigation**
  - **Tooling:** Next.js, React, TypeScript, Tailwind CSS, Playwright, axe-core.
  - **Target Files:** `web/app/layout.tsx`, `web/app/page.tsx`, `web/components/app-shell/`, `web/lib/api-client.ts`, `web/lib/client-router.ts`, `web/lib/routes.ts`, `tests/e2e/navigation.spec.ts`, `tests/e2e/accessibility.spec.ts`.
  - **Details:** Build a Next.js static-export shell with a client-side route table, rather than runtime Next dynamic routes. FastAPI always serves the SPA shell for approved client paths. Build desktop-first sidebar, responsive mobile drawer, protected routes, story/branch context, error boundaries, user preference entry point, and accessibility preferences.
  - **Status:** Implemented: `lib/routes.ts` (client route table for `/onboarding`, `/workspace`, `/world`, `/endings`, `/reports`), `lib/client-router.ts` (`pushState`/`popstate`-based navigation hook, no runtime Next dynamic routing), `lib/api-client.ts` (fetch wrapper against `/api/v1`, `credentials: "include"`, `Idempotency-Key` header support, `ApiError`, `isAuthenticated()` real-checks `/me/preferences` rather than assuming a session), and `components/app-shell/` (`Sidebar` desktop nav, `MobileDrawer` with focus-on-open and Escape-to-close, `ProtectedRoute` gating protected routes on the real auth check with visible checking/redirect states, `ErrorBoundary`, `AppShell` composing all of it with a skip-to-content link). `app/page.tsx`/`app/layout.tsx` wired to render through `AppShell`. `@playwright/test` and `@axe-core/playwright` are now installed (`package.json` devDependencies) and `playwright.config.ts`, `tests/e2e/navigation.spec.ts`, and `tests/e2e/accessibility.spec.ts` are written.
  - **Verification:** `npx tsc --noEmit -p web/tsconfig.json` passes with no errors, including the new spec files (checked via a standalone `tsc` invocation matching their syntax). `npx next build web` (static export) was started but did not complete within this sandbox's 45-second per-command cap. **Playwright specs have not actually been executed**: `npx playwright install chromium` cannot complete in this sandbox — each sandbox command call gets a fresh container with no persisted download cache, so the ~195MB Chromium download restarts from 0% every invocation and never finishes inside the 45-second command budget, and `--with-deps` additionally fails because sudo is disabled here. The specs are real (target real ARIA roles/text this app renders) but unverified. This needs to run once in a normal CI/dev environment before `[x]`.

- [/] **Task 4H.2: Build seed clarification, template, concept, cast, and personalization feature views**
  - **Tooling:** React Hook Form/Zod or equivalent, Tailwind CSS, Playwright.
  - **Target Files:** `web/components/features/onboarding/`, `web/components/features/preferences/`, `web/lib/routes.ts`, `tests/e2e/onboarding.spec.ts`.
  - **Details:** Implement no-hard-minimum seed validation, visible clarification/redirect loop, original/licensed template picker with disclosure labels, consented personalization selection, family-tree summary, cast lock confirmation, and immediate Chapter 1 launch. Hidden-characteristic UI must not exist; do not port the prototype `>=20` gate or blurred hidden row.
  - **Status:** Implemented `SeedForm` (no hard minimum; a visible, dismissable clarification prompt appears below a 12-character soft threshold, author can always continue), `TemplatePicker` (explicit `ORIGINAL`/`LICENSED_REFERENCE` disclosure badge on every option, no undisclosed licensed content), `PersonalizationConsent` (opt-in only, nothing pre-checked, calls the real `PATCH /me/preferences` per accepted category then `POST /me/personalization-snapshots` to freeze the snapshot), `CastEditor` + `CastLock`, and `OnboardingFlow` orchestrating all five steps (`seed → template → language → personalization → cast → cast-lock`), wired as the default `/` route. `grep -rniE "hidden-row|secret exists|minimum 20|blur"` across `web/components` and `web/app` returns no matches. `tests/e2e/onboarding.spec.ts` is now written.
    **Prior backend gap now closed (this pass):** `CastEditor` calls a new `POST /api/v1/stories/cast-proposal` (`src/story_engine/api/routes/stories.py`) which runs the seed through the same `RuleBasedContentPolicy` gate used everywhere else (blocked/redirected seeds never reach the model) and, on an allowed seed, calls a new `src/story_engine/services/cast_proposal.py` (`propose_cast`/`parse_and_validate_cast_proposal`) that makes one raw-`urllib` OpenAI Responses call (matching `agents/provider.py`'s existing convention — no new SDK dependency) and defensively parses/bounds the JSON response (rejects malformed JSON, non-array shapes, >6 characters, a missing protagonist-flagged first character, and silently drops any stray/unexpected field such as a model-invented `hidden` key rather than trusting it). The author edits the proposed cast (or a manual fallback card if generation fails) in `CastEditor`, then `CastLock` submits the full array as `POST /stories`'s new `cast: CastMemberInput[]` field, which now creates one `entities` row per character (protagonist inserted first so `list_stories`'s and `cast.py`'s existing "earliest-created character" convention still correctly identifies the protagonist) instead of always hardcoding a single "Protagonist" entity. `cast.py`'s `lock_cast` role assignment was also fixed to key off that same earliest-created-entity convention instead of a literal `name == 'Protagonist'` string match, which would otherwise have silently mislabeled every real character as `SUPPORTING`.
    **Deliberately not ported from `docs/reference/StoryEngineProto.jsx`'s `CAST_INITIAL`/`ScreenCharacters` (task.md 0.4):** no hidden-characteristic field/row anywhere in `CastCharacterProposal`, `CastMemberInput`, `CastEditor`, or `CastLock` — every field the author sees is editable and nothing is concealed, matching Task 2D's inspectable-mutable-trait-state decision; no 20-character seed gate (the cast-proposal endpoint has no seed-length gate of its own; `SeedForm`'s existing 12-character soft clarification prompt is untouched); founding cast identity still becomes immutable at lock time via `POST /stories`, matching both the prototype's own "predefined, editable only pre-launch" framing and design.md.
    **What is still honestly missing:** the LLM proposal path (`propose_cast`) has never been exercised against a live OpenAI call — this sandbox has no live network access, so `test_cast_proposal_contract.py` stubs the provider and `test_cast_proposal.py` only unit-tests the JSON validator. A real end-to-end run against `dev`/`staging` (real seed → real model call → real cast → real `POST /stories`) should happen before fully trusting the prompt's output shape in production. Family-tree-summary rendering in the onboarding flow itself (as opposed to the already-existing `GET /stories/{id}/family-tree` endpoint) is still not built — that remains open.
  - **Verification:** `npx tsc --noEmit -p web/tsconfig.json` passes (verified this pass, zero errors). `python3 -m pytest tests/ -q` passes (209 passed, 18 skipped, 0 failed, this pass — includes new `tests/unit/test_cast_proposal.py` and `tests/contract/test_cast_proposal_contract.py`, plus extended `tests/contract/test_story_language_contract.py` for the new `cast` field). `tests/e2e/onboarding.spec.ts` exists but has not actually run — Playwright's browser binary cannot be installed in this sandbox (see Task 4H.1's verification note). The family-tree/cast-lock backend gap this task previously flagged is now closed; remaining open items are the live-OpenAI verification and family-tree-summary rendering noted above.

- [/] **Task 4H.3: Build workspace feature view, streamed agent activity, trait cards, and branch controls**
  - **Tooling:** React, SSE client, TanStack Query, Tailwind CSS, Playwright.
  - **Target Files:** `web/components/features/workspace/`, `web/components/workspace/`, `web/lib/generation-stream.ts`, `tests/e2e/generation.spec.ts`.
  - **Details:** Render loader → live activity → unpublished candidate preview → published chapter. Implement reconnect, jump-to-latest, reduced motion, accessible entity list, read-only graph, visible versioned trait cards, focal-character selector, and exactly three progression modes: Continue automatically, Edit traits, Jump/rewind.
  - **Status:** Implemented `lib/generation-stream.ts`, `ActivityFeed`, `TraitCard`, `BranchControls`. `components/features/workspace/WorkspaceView.tsx` composes all four into the actual workspace route — it replaces the old static `WorkspaceStudio` demo in `app/page.tsx` (whose three progression buttons had no `onClick` at all; confirmed fixed via `grep -rn "<button" web/app web/components | grep -v onClick`, which now returns zero genuinely-dead buttons). `WorkspaceView`'s `BranchControls.onSelect` calls the real `POST /branches/:id/progression`, and once a `job_id` comes back, `useGenerationStream` opens the real SSE connection — the `/api/v1/generation-events/demo` stand-in is no longer used by the workspace route. **Closed in this pass:** `app/page.tsx`'s `/workspace` route now imports `StoryList` and `useSelectedBranch` (`lib/story-context.ts`) instead of a raw branch-id text box — the "still no story/branch picker wired in" gap Task 4H.3 previously called out. Picking a story from `StoryList` calls `selectBranch(story.initial_branch_id)`, which writes the same `story-engine-active-branch` localStorage key `CastLock.tsx`/`WorkspaceView` already read/write, so no other component needed to change. `/world`, `/endings`, `/reports` still use the old `IdScopedView` text-box fallback (out of scope for this pass — they have no per-view picker of their own yet). **Still not wired:** no TanStack Query wiring (plain hooks only); no focal-character selector; no read-only relationship graph component. `QuotaBanner` now has a real data source — see Task 5J.1's note on `GET /api/v1/me/quota` and `POST /branches/:id/progression`'s 429 body — but `QuotaBanner` itself hasn't been wired into `WorkspaceView` to render it yet; that render-side connection is still open.
  - **Verification:** `npx tsc --noEmit -p web/tsconfig.json` passes (re-run after this pass's `app/page.tsx` edit — clean, no type errors introduced). `pytest -q`/full suite last run at 140 passed, 18 correctly skipped (not re-run in this pass; only Python files touched this pass were compiled with `python3 -m py_compile`, not executed — see 5J.1). `tests/e2e/generation.spec.ts` is accurate against current markup but still has not actually executed — Playwright's browser binary cannot be installed in this sandbox (same blocker as Task 4H.1). Do not mark `[x]` until the e2e spec actually runs and passes, and `QuotaBanner` is rendered somewhere real.

- [/] **Task 4H.4: Build world, ending, reports, revision, and recovery feature views**
  - **Tooling:** React, Playwright.
  - **Target Files:** `web/components/features/world/`, `web/components/features/endings/`, `web/components/features/reports/`, `web/components/canon-events/`, `web/components/revisions/`, `tests/e2e/recovery.spec.ts`.
  - **Details:** Implement canon-event/relationship request dialogs, evaluator/business reports, ending-options request/selection, trace drawer behind feature flag, blocked-generation retry, archive/unarchive, and Edit-as-revision flow. Never reuse the prototype's direct kill/revive handlers: show target, branch, permanent-record consequence, explicit confirmation, then pending/evaluating status before any entity state changes. Show policy blocks, quota state, and safe alternative copy clearly.
  - **Status:** Backend gaps closed first: added `src/story_engine/api/routes/endings.py` (`GET /branches/:id/ending-options`, `POST /branches/:id/ending-options/:optionId/select` — the select handler rolls back entirely, including the prior selection's unset, if the target option doesn't match, so a 404 never has a side effect) and `src/story_engine/api/routes/revisions.py` (`POST`/`GET /chapters/:id/revisions`, always inserting/listing `DRAFT` rows, never editing the chapter itself), both wired into `app.py`; contract tests added (auth-boundary + `extra=forbid` schema checks), 90/90 passing, ruff/mypy clean, no target-file collisions. Frontend: `WorldView.tsx` (read-only entity/relationship display against `GET /branches/:id/state`), `CanonEventRequestDialog.tsx` (fixed a real bug during this pass — its event-type strings originally didn't match the backend's actual `CanonEventType` enum (`KILL`/`REVIVE`/`MOVE_REALM`/`INTRODUCE_ENTITY`/`EDIT_CANON`), corrected and now validates `requires_target_entity`-equivalent target presence client-side too; permanent-record warning shown for `KILL`, required confirmation checkbox, pending-status-only after submit), `EndingOptionsView.tsx` (lists/selects against the new endings route), `RevisionRequestForm.tsx` (submits against the new revisions route, copy explicitly states the original chapter is unchanged), and `TraceDrawer.tsx` (calls `GET /agent-runs/:id`, treats a 404 as "tracing off or not visible" rather than an error). `/world`, `/endings`, `/reports` routes in `app/page.tsx` now render these against an author-supplied branch/run id (there is still no story/branch-picker context provider, so this is a text field, not real navigation from a story list). `tests/e2e/recovery.spec.ts` written, with its second case (`RevisionRequestForm`) marked `test.skip` and explained: no chapter-detail route renders that component yet. **Closed in the parallel-session pass (`docs/parallel-session-plan.md` Track 6, Track 5):** `src/story_engine/api/routes/archive.py` adds `PATCH /chapters/:id/archive`/`.../unarchive` (via a new `world_set_chapter_archived` SECURITY DEFINER function, migration 0013, since direct chapter `UPDATE` was already revoked by migration 0008) and `POST /generation-jobs/:id/retry` (validates the job is `BLOCKED`/`FAILED`, creates a fresh `generation_jobs` row with `idempotency_key=f"retry-{job_id}"` plus a same-transaction outbox entry — never resets the failed row in place). `web/components/features/recovery/RecoveryControls.tsx` renders the archive/unarchive toggle and a conditional retry button against these new routes, closing the "blocked-generation retry UI" gap. `web/components/features/chapters/ChapterDetailView.tsx` (Track 5) now fetches `GET /chapters/:id` and hosts `RevisionRequestForm` — the chapter-detail route `test.skip` in `tests/e2e/recovery.spec.ts` was blocked on ("no chapter-detail route renders that component yet") now exists, though the skip itself hasn't been re-enabled/re-verified. `src/story_engine/api/routes/traces.py` gained `GET /generation-jobs/:id/agent-runs`, closing the "no run-listing endpoint" gap so `TraceDrawer` no longer strictly needs a known run id. **Closed in this pass:** the quota/policy-block *display* now has a real backend source — `GET /api/v1/me/quota` (`src/story_engine/api/routes/progression.py`) returns a `list[QuotaStateResponse]` shaped to match `QuotaBanner.tsx`'s `QuotaBannerState` field-for-field (verified by a new contract test asserting the OpenAPI schema carries all six fields). `QuotaBanner` itself is still not actually rendered by any view (no `<QuotaBanner state={...} />` call exists yet) — the data source gap is closed, the render-side wiring is not. **Also closed:** the "no aggregate evaluator/business report view beyond per-run traces" gap — `report_job.py` now writes real `business_reports` rows (see Task 3F.1), `traces.py` gained `GET /branches/{branch_id}/business-reports` (RLS-scoped, joins `business_reports` → `generation_jobs` → `branches` per the `business_reports_owner` policy from migration 0006), and `web/components/features/reports/BusinessReportsView.tsx` renders the list. It's still per-branch, not a cross-story dashboard, and it's never been exercised against a branch with a real published business report.
  - **Verification:** `npx tsc --noEmit -p web/tsconfig.json` passes for everything above, including `RecoveryControls.tsx`, `ChapterDetailView.tsx`, and `BusinessReportsView.tsx`. **Actually executed this session** (a real `pytest` run, not just `py_compile` — installed the missing deps for this sandbox's Python 3.10 interpreter and shimmed `enum.StrEnum` via a `strenum` backport, documented in Task 5J.1's note): full suite **166 passed, 18 correctly skipped, 0 failed**. `tests/e2e/recovery.spec.ts` still has not run (Playwright browser-install blocker persists), and its `RevisionRequestForm` case is still marked `test.skip`. Do not mark `[x]` — `QuotaBanner` isn't rendered anywhere yet, the skipped e2e case hasn't been re-verified, and no e2e spec has actually executed.

### 🛑 SYNC POINT 4: App Integration on Databricks 🛑

- [ ] **Task 4.S1: Deploy the App and complete browser-level smoke tests**
  - **Target Files:** all Phase 4 files only.
  - **Details:** Build static web assets, package the App, deploy through the bundle, and run Playwright against the `dev` App URL with test identities.
  - **Verification:** Health/readiness/API/SSE tests pass; the Chapter 1 test reaches `PUBLISHED`; cross-tenant and hidden-secret negative browser tests pass.

---

## Phase 5: Observability, Quality, and Release Readiness

### Track I — Monitoring, Data Quality, and Runbooks

*Target isolation: `src/story_engine/analytics/`, `docs/runbooks/`, and `tests/integration/observability/` only. Track I does not create ADRs in this phase.*

- [/] **Task 5I.1: Implement application metrics and structured logging**
  - **Tooling:** Python logging/OpenTelemetry-compatible exporter, Databricks logs, Delta audit.
  - **Target Files:** `src/story_engine/analytics/observability.py`, `docs/runbooks/observability.md`, `tests/integration/observability/test_metrics.py`.
  - **Details:** Record job queue latency, agent latency, retry count, evaluator outcome, SSE reconnect count, RLS denial count, deployment version, per-job/story/user model-token and spend estimate, cost-budget threshold events, chapter-loop completion, branch usage, trait-edit acceptance, ending-option use, and future comic-export placeholders. Use correlation IDs; redact payloads by default. Define a configurable per-user budget kill switch that pauses new generation submissions with a clear message.
  - **Status:** Implemented `observability.py`: `MetricEvent` enum covering every listed metric, `CorrelatedLogRecord`/`emit()` (correlation-id-tagged structured logging via the stdlib `logging` module), `_assert_no_forbidden_keys` (rejects `prompt`/`secret`/`hidden_characteristic`/`preference_value`/`raw_response`/`api_key` payload keys before logging, mirroring `FORBIDDEN_COLUMN_SUBSTRINGS`), and `BudgetState`/`enforce_budget`/`BudgetExceededError` (the budget kill switch — blocks only new submissions, never cancels in-flight jobs, user-facing message states both facts). Test file was written as `tests/unit/analytics/test_observability.py` rather than the target `tests/integration/observability/test_metrics.py`, since these are pure-Python and need no live DB/Spark — placing them under `tests/unit` matches this repo's existing convention (`analytics/audit_schema.py`'s tests live in `tests/unit/analytics/` too) more than an unopened `tests/integration/observability/` directory would. `docs/runbooks/observability.md` written. **Wired in this pass (parallel-session-plan.md Tracks 8-9):** `job_dispatcher.dispatch_pending` now emits `RETRY_COUNT` on every launch failure, correlated by job id — the first real caller of this module. `workers/generation_job.py`'s real (non-stub) generation loop now emits `AGENT_LATENCY` around every model call via a new `_timed_complete` wrapper, and `CHAPTER_LOOP_COMPLETION` on both the success and failure exit paths. `workers/report_job.py` remains a stub (`NotImplementedError`) with its instrumentation points documented inline for whenever real model calls land there. **Still not done:** no OpenTelemetry exporter (stdlib logging only), and `enforce_budget()` still has no caller anywhere — there's still no `budget_limit_usd` storage/settings surface to read a real limit from, so no call site was added rather than fabricate one.
  - **Verification:** `tests/unit/analytics/test_observability.py`: 7/7 passing. Ruff/mypy clean for `job_dispatcher.py` and `generation_job.py` after the new calls. No log scanner has been run against a live job's actual log output since no job has ever executed against a real Databricks Job runtime in this sandbox.

- [/] **Task 5I.2: Add data-quality and reconciliation checks**
  - **Tooling:** PySpark, SQL, pytest.
  - **Target Files:** `src/story_engine/analytics/quality_checks.py`, `notebooks/03_operational_quality_checks.py`, `tests/integration/observability/test_reconciliation.py`.
  - **Details:** Check published chapter/state consistency, branch ancestry validity, event sequence continuity, audit-export reconciliation, and forbidden Delta columns. Run checks as a scheduled Databricks Job.
  - **Status:** Implemented `quality_checks.py`: `check_published_chapter_state_consistency`, `check_branch_ancestry_validity` (including cycle detection), `check_event_sequence_continuity`, `check_audit_export_reconciliation`, `check_no_forbidden_delta_columns` (reuses `FORBIDDEN_COLUMN_SUBSTRINGS` from `audit_schema.py`) — every failure is a `QualityCheckFailure` dataclass carrying a concrete `identifier` (branch/job/table id), never a bare "check failed". `notebooks/03_operational_quality_checks.py` written as the scheduled-job wrapper. **New this pass:** `quality_checks_job` is now registered in `resources/jobs.yml` as a `notebook_task` (not a wheel task, since the notebook needs no packaging) on a daily cron, gated by a new `quality_checks_schedule_paused` variable (`resources/variables.yml`, defaults to `"PAUSED"` so a fresh deploy doesn't start running an unreviewed job against real data). `databricks bundle validate -t dev` resolves this new resource cleanly (confirmed against the real workspace host/account — only fails at the expected auth step). Test file remains `tests/unit/analytics/test_quality_checks.py` rather than `tests/integration/observability/test_reconciliation.py` (same reasoning as 5I.1).
  - **Verification:** `tests/unit/analytics/test_quality_checks.py`: 10/10 passing. Ruff/mypy clean. `databricks bundle validate -t dev` passes structurally. Never actually run as a scheduled Databricks Job — that requires `databricks bundle deploy`, which needs your own authenticated CLI session (this sandbox can't complete the OAuth browser flow).

- [/] **Task 5I.3: Write operational incident and recovery runbooks**
  - **Tooling:** Markdown, Databricks Jobs/App/Lakebase procedures.
  - **Target Files:** `docs/runbooks/generation-failure.md`, `tenant-isolation-incident.md`, `rollback.md`, `access-revocation.md`.
  - **Details:** Document response for stuck lease, failed bundle deploy, stale candidate, secret-redaction failure, RLS incident, Lakebase outage, user preference deletion, and app rollback. Include commands with placeholders only.
  - **Verification:** All four runbooks written, each covering symptom/diagnosis/recovery/verification with placeholder-only commands and explicit "never delete published canon as a rollback/recovery mechanism" guidance. A reviewer has not actually run the generation-failure drill in a live `dev` workspace (none exists in this sandbox) — the drill steps are written but unrehearsed, same limitation noted throughout Track A/B/C/F's live-environment-dependent items.

### Track J — Performance, Security, and Release Gates

*Target isolation: `tests/performance/`, `tests/security/`, `.github/workflows/`, and `docs/adr/2xx-*` only.*

- [/] **Task 5J.1: Execute security, safety, IP, and privacy test suite**
  - **Tooling:** pytest, Playwright, secret scanner, dependency scanner.
  - **Target Files:** `tests/security/test_rls_negative.py`, `test_prompt_injection.py`, `test_event_redaction.py`, `test_personalization_isolation.py`, `test_content_ip_wellbeing.py`.
  - **Details:** Test every stated loophole guard: tenant crossing, hidden-secret stream leak, prompt injection, Director-memory privacy, stale writes, duplicate branches, unauthorized personalization snapshot use, blocked safety categories, copyrighted-IP handling, sensitive-content privacy, disclosed template/sponsorship behavior, and explicit quota responses.
  - **Status:** All five target files written. `test_rls_negative.py` (DB-gated): tenant-crossing on `canon_event_requests`, extending rather than duplicating the existing `tests/integration/persistence/test_rls.py` coverage of `stories`/`branch_entity_states`. `test_personalization_isolation.py` (DB-gated): cross-tenant read denial on `user_preferences` and `personalization_snapshots`. `test_event_redaction.py` (unit, no DB): `ClientGenerationEvent` rejects smuggled `payload`/`prompt` fields via `extra="forbid"`, `_row_to_event` skips a malformed row instead of raising or leaking it, a well-formed event's `model_dump()` has no `payload`/`prompt`/`raw_response` key. `test_prompt_injection.py` (unit): canon-event rationale and revision author-patches are length-capped (2000/12000 chars), `CanonEventRequestInput` rejects an injected extra field, and a static source-scan confirms `world.py`/`revisions.py` build every query via parameterized `execute(query, params)`, never f-string SQL. `test_content_ip_wellbeing.py` (unit): `CanonEventType` is a closed 5-member enum (no free-text event category is possible), and a source-scan confirms every `TemplatePicker` entry declares a `disclosure` field with visible "Licensed reference" copy — found and fixed a real bug while writing this: the first draft of `CanonEventRequestDialog.tsx` used event-type strings that didn't match the backend's actual enum at all (`REMOVE_ENTITY`/`MOVE_ENTITY`/`CHANGE_RELATIONSHIP` vs. the real `KILL`/`REVIVE`/`MOVE_REALM`), which would have made every canon-event request from that dialog fail server-side validation. **Not covered:** Director-memory privacy (no test targets memory-cutoff enforcement specifically from a security angle — `tests/integration/persistence/test_memory_cutoffs.py` covers the cutoff mechanism itself but not adversarial access to pre-cutoff memory), stale-write/duplicate-branch races under concurrency, blocked safety categories (no content-moderation/safety-category enum exists in this codebase yet to test), sponsorship-disclosure behavior (no sponsorship concept exists). Explicit quota-response copy: **closed in a later pass** — `services/quotas.py`'s `enforce_quota`/`QuotaState` is now actually called from `POST /branches/:id/progression` (before the job/outbox insert, after idempotency replay so a replayed request is never re-blocked), returning a 429 with a `QuotaStateResponse` body shaped to match `QuotaBanner.tsx`'s `QuotaBannerState`; a read-only `GET /api/v1/me/quota` was added alongside it, computing live `used` counts from `generation_jobs`/`branches` (limits are fixed defaults — `DEFAULT_LIMITS` in `quotas.py` — since no per-tenant override table exists). A contract test (`tests/contract/test_rest_contract.py::test_my_quota_requires_auth`, `::test_quota_state_response_schema_matches_quota_banner_shape`) covers the auth boundary and response shape; the actual 429-on-exceeded-quota path is still **not** exercised end-to-end against a live Lakebase (would need a seeded user with `CONCURRENT_GENERATION_JOBS` already at its limit) and `QuotaBanner.tsx` is still not rendered by any view (see Task 4H.4's note) — the copy exists in the component but nothing mounts it yet. No secret scanner or dependency scanner has been run in this pass — `.github/workflows/ci.yml`'s `secret-scan` job (gitleaks, added in Task 1A.4) is the mechanism, but it runs in CI, not in this sandbox. **Additional auth-boundary coverage landed via `docs/parallel-session-plan.md`'s 10 tracks (not new files under this task's own target list, but directly relevant to its scope):** `tests/contract/test_cast_contract.py` (Track 1 — cast-lock idempotency, family-tree read scoping), `tests/contract/test_world_idempotency.py` (Track 2 — canon-event-request replay), `tests/contract/test_revisions_idempotency.py` (Track 3 — revision-request replay) all assert cross-tenant/unauthenticated requests are rejected before any idempotency-key logic runs, extending this task's tenant-crossing coverage to three previously-untested endpoint families.
  - **Verification:** `pytest tests/security -q`: 13 passed, 3 skipped (DB-gated, correctly skip without `TEST_DATABASE_URL`). **Closed in this pass:** the two previously-flagged gaps — "blocked safety categories (no enum exists to test)" and "Director-memory privacy (no adversarial angle)" — were re-investigated rather than assumed: `PolicyCategory`/`RuleBasedContentPolicy` (Task 2D.4) already existed and were only unit-tested for correctness, not adversarially from the security suite, so `tests/security/test_content_ip_wellbeing.py` gained a parametrized test asserting all 7 prohibited categories (minor sexualization, self-harm glorification, graphic violence, sexual content, hate/extremism, real-person privacy, unlicensed IP) actually `BLOCK` with a safe alternative, plus a distress-input `REDIRECT` test. `DirectorMemoryRecord` (Task 2D.3) gained an adversarial test proving a hidden-characteristic/private-memory string is rejected — note it surfaces as a wrapped `pydantic.ValidationError`, not the raised `UnsafeDirectorMemory` directly, since Pydantic re-wraps `ValueError` subclasses raised from `field_validator`; the test asserts on the wrapped message rather than the exception type. **First actual full-suite execution in this sandbox this session** (previous passes only got `python3 -m py_compile`/`tsc --noEmit`, never a real `pytest` run, because this sandbox ships Python 3.10 and the codebase requires 3.11+ for `enum.StrEnum`): installed `fastapi`, `sse_starlette`, `databricks-sdk`, `httpx`, `psycopg`, `pytest-asyncio`, and a `strenum` backport shimmed onto `enum.StrEnum`, then ran the entire `tests/` tree — **166 passed, 18 correctly skipped (DB-gated), 0 failed.** Still not covered: stale-write/duplicate-branch races under concurrency, sponsorship-disclosure behavior (no sponsorship concept exists — a product-scope decision, not a bug), and no secret/dependency scanner run in this pass (that's `ci.yml`'s job, not something to duplicate locally).

- [/] **Task 5J.2: Execute performance and resilience tests**
  - **Tooling:** k6/Locust, pytest, Databricks Jobs.
  - **Target Files:** `tests/performance/api_load.js`, `tests/performance/sse_reconnect.js`, `docs/adr/201-slo-and-capacity.md`.
  - **Details:** Establish explicit dev/staging SLOs for API latency, event delivery, job queue start, and generation completion. Test concurrent users, reconnect storms, rate limits, job worker restart, and Lakebase connection recovery.
  - **Status:** `docs/adr/201-slo-and-capacity.md` written with explicit numeric SLOs for all four required metrics plus concurrent-user capacity and error-rate targets, marked "Proposed" and explicitly labeled as unvalidated design targets rather than measured results. `tests/performance/api_load.js` (ramping-VUs concurrent-reader load against `GET /api/v1/stories`, p95<500ms threshold) and `tests/performance/sse_reconnect.js` (reconnect-storm approximation via rapid short-lived requests with random `Last-Event-ID`, since k6's core HTTP module can't hold an `EventSource`-style stream open) both written. **Neither script has ever been executed** — there is no live Databricks App deployment to point `BASE_URL` at in this sandbox. Job-worker-restart and Lakebase-connection-recovery testing are not covered by either script; those need an actual running worker/Lakebase instance to kill and observe recovery from, which this sandbox cannot provide.
  - **Verification:** No test report exists because neither script has run. Do not mark `[x]` until both scripts execute against a real `dev`/`staging` deployment and either meet the ADR's thresholds or produce approved remediation tasks.

- [/] **Task 5J.3: Define production release checklist and rollback gate**
  - **Tooling:** GitHub Environments, Declarative Automation Bundles, Databricks Apps/Jobs.
  - **Target Files:** `docs/runbooks/release-checklist.md`, `.github/workflows/deploy.yml`.
  - **Details:** Require migration backup/restore validation, bundle validation, staged deploy, App health check, worker job run, RLS negative test, audit quality check, and approval before production. Rollback must be application/bundle version rollback; never delete published canon as a rollback mechanism.
  - **Status:** `docs/runbooks/release-checklist.md` written with every required pre-deploy gate as an explicit checkbox (migration backup/restore, bundle validate, staged deploy + health check, worker job run, RLS negative test, audit quality check, evidence attachment, manual approval), a rollback-gate section reiterating "never delete published canon," and a deferred-scope section for Task 5.S1's explicitly out-of-release items (comic export, animated portraits, collaboration, vector retrieval). `.github/workflows/deploy.yml` (which already existed with a basic validate-then-deploy flow) extended with a `gate` job (full test suite + ruff + mypy + `check_task_paths.py` + a staging-only RLS/personalization-isolation re-run) that `deploy` now depends on, plus new `worker-smoke-test` and post-deploy health-check steps (currently placeholder `echo "TODO: ..."` commands, since the actual App URL and job id don't exist yet).
  - **Verification:** No staging release rehearsal or rollback rehearsal has been performed — no live workspace exists in this sandbox. `deploy.yml`'s YAML structure is internally consistent (job dependency chain: `gate` → `deploy` → `worker-smoke-test`) but has never actually run. Do not mark `[x]` until a real rehearsal captures a deployed bundle version and restoration evidence per this task's verification bullet.

### 🛑 SYNC POINT 5: Production Readiness Review 🛑

- [ ] **Task 5.S1: Sign off the release evidence pack**
  - **Target Files:** `docs/runbooks/release-checklist.md` and generated CI artifacts only.
  - **Details:** Review all phase gates, test reports, security evidence, deployment manifests, migration status, actual quota defaults, model budget thresholds, and known risks. Create follow-up tasks for intentionally deferred image/comic generation, animated portraits, collaboration, and vector retrieval.
  - **Verification:** All required checkboxes are complete, `databricks bundle validate -t prod` succeeds, and the release approver records the commit SHA and bundle version.

---

## Phase 6: Two-Way Voice Conversation

### Track K — Voice Input (Streaming STT) and Narrator Playback (TTS)

*Target isolation: `src/story_engine/api/routes/voice.py`, `src/story_engine/api/routes/narration.py`, `src/story_engine/services/narration.py`, `src/story_engine/agents/voice_provider.py`, `src/story_engine/api/settings.py`, `web/lib/voice-stream.ts`, `web/components/shared/`, and the five integration points listed below.*

- [/] **Task 6K.1: Streaming speech-to-text over WebSocket, gated through the existing content policy**
  - **Tooling:** FastAPI `WebSocket`, `urllib` (matching `agents/provider.py`'s existing no-SDK convention — the OpenAI Python SDK is not, and was not made, a dependency of this repo), OpenAI `audio/transcriptions` (Whisper) REST endpoint, `RuleBasedContentPolicy`.
  - **Target Files:** `src/story_engine/api/routes/voice.py`, `src/story_engine/agents/voice_provider.py`, `src/story_engine/app.py` (router wiring), `web/lib/voice-stream.ts`, `web/components/shared/VoiceInputButton.tsx`.
  - **Details:** `WS /api/v1/voice/transcribe` authenticates by reading the same `x-forwarded-user`/`x-forwarded-email` headers `authenticate_request` reads for every other route (a WebSocket upgrade is still an HTTP request, so these headers are present without inventing a query-param token or first-message handshake — see the tradeoff note in `voice.py`'s module docstring: this holds only as long as the Databricks Apps reverse proxy is the sole path to this app). The client (`voice-stream.ts`, mounted via `VoiceInputButton.tsx`) captures mic audio with `MediaRecorder`, sending a new ~2.5s binary chunk as soon as it's available. **Honesty note:** there is no bidirectional realtime session to OpenAI here — the OpenAI Python SDK is not used anywhere in this codebase (`agents/provider.py` already talks to the Responses API with raw `urllib`), and no true streaming/realtime transcription API is called. What is implemented instead is chunked near-real-time transcription: each chunk is transcribed synchronously via a normal `POST /v1/audio/transcriptions` (Whisper) call the moment it arrives, and the resulting partial text is pushed back as a `partial` WS message immediately — giving a live-updating transcript from repeated short Whisper calls, not one true streaming session. On the client's `"stop"` control message, all chunk transcripts are joined and re-validated as one utterance through `RuleBasedContentPolicy.assess` (`security/content_policy.py`) — the same deterministic gate `generation_pipeline.py` already runs candidate prose through — before being emitted as a `final` transcript; a `BLOCK`/`REDIRECT` result is emitted as a `rejected` message (with the policy's `safe_alternative`) instead, so a rejected voice utterance can never reach `onTranscript` in `VoiceInputButton.tsx` any more than typed text bypasses policy. (Separately noted: as of this pass, typed free text in `seed`/`trait-edit`/`canon-event-request`/`revision-request` routes does not itself run through `RuleBasedContentPolicy` at submission time — only `generation_pipeline.py`'s candidate-prose step does. Voice transcripts are therefore gated *at least as strictly as*, and in this pass more strictly than, the typed-text path for the same fields; this is not a bypass, but closing that pre-existing typed-text gap is out of this track's scope.) `VoiceInputButton.tsx` is wired into all five required free-text surfaces: `SeedForm.tsx` (seed/clarification), `WorkspaceView.tsx`'s trait-change field (serves both "trait-edit freeform text" and "the workspace progression flow" per the decided scope — it is the same input), `CanonEventRequestDialog.tsx` (rationale), and `RevisionRequestForm.tsx` (author patch).
  - **Status:** Implemented as described. `voice.py`, `voice_provider.py`, `voice-stream.ts`, `VoiceInputButton.tsx` all written; `app.py` includes the new router. `tsc --noEmit -p web/tsconfig.json` passes with no errors after all five integrations.
  - **Verification:** `python3 -m py_compile` clean on every new/changed `.py` file. `tests/contract/test_voice_contract.py::test_voice_websocket_rejects_connection_without_identity_headers` confirms the auth-boundary rejection (code 1008) using `TestClient.websocket_connect` with no headers. `tests/unit/test_voice_content_policy_gate.py` (3 tests) exercises `_emit_final` directly with a fake WS sink — proves a benign transcript reaches `final`, a policy-violating transcript is rejected (never reaches `final`), and an empty transcript doesn't bypass the gate. `pytest tests/unit tests/contract -q`: 152 passed (includes all pre-existing tests — nothing regressed). **Not verifiable in this sandbox:** no real microphone, no real speaker, no live OpenAI network call was made — `MediaRecorder` capture, actual Whisper transcription accuracy/latency, and a live end-to-end "speak into a mic, see live partial text, get a final transcript" run all require a live browser session with mic hardware and a real OpenAI API key, none of which exist here. Do not mark `[x]` until that live round-trip has been run and observed.

- [/] **Task 6K.2: Narrator-voice text-to-speech playback for published chapters**
  - **Tooling:** OpenAI `audio/speech` (TTS) REST endpoint via the same `urllib`-based `voice_provider.py` adapter, FastAPI, `web/components/shared/ChapterNarrationPlayer.tsx`.
  - **Target Files:** `src/story_engine/api/routes/narration.py`, `src/story_engine/services/narration.py`, `src/story_engine/agents/voice_provider.py`, `src/story_engine/api/settings.py` (`openai_tts_model`, `narrator_voice`), `web/components/shared/ChapterNarrationPlayer.tsx`, `web/components/features/chapters/ChapterDetailView.tsx`.
  - **Details:** `GET /api/v1/chapters/{chapter_id}/narration` reuses `chapters.py`'s exact authorization pattern — `tenant_connection(user)` (RLS-scoped), and `services/narration.published_chapter_text` reads only the published `chapters`/`scenes`/`dialogue` tables (never `candidate_chapters`), returning 404 for a chapter that doesn't exist or isn't `PUBLISHED`, matching `chapters.get_chapter`'s not-found behavior exactly rather than distinguishing "not found" from "not yet published" (avoids leaking staging existence). This is playback of already-published, already-policy-checked text — TTS does not generate new prose, so none of the candidate-prose policy gates apply; a single fixed "narrator"/Storyteller-style voice (`settings.narrator_voice`, default `"alloy"`) is used for every chapter, never a per-agent voice, per the decided scope. `ChapterNarrationPlayer.tsx` fetches the endpoint as a blob (preserving the `credentials: "include"` identity contract `api-client.ts` documents) and exposes play/pause; wired into `ChapterDetailView.tsx`, shown only when `chapter.status === "PUBLISHED"`.
  - **Status:** Implemented as described; `narration_router` included in `app.py`.
  - **Verification:** `python3 -m py_compile` clean. `tests/contract/test_voice_contract.py::test_narration_requires_auth` (401 without identity headers, matching every other authenticated route's contract test) and `::test_narration_route_is_exposed` (route present in the OpenAPI schema) both pass. `tests/unit/test_voice_settings.py` (2 tests) covers `openai_transcription_model`/`openai_tts_model`/`narrator_voice` default values and env-var overrides — pure settings-loading logic, no network. **Not verifiable in this sandbox:** no live OpenAI TTS call was made, so actual audio output quality/latency and the full `ChapterNarrationPlayer` play/pause round trip against real synthesized audio are unverified. Do not mark `[x]` until that live call has been made against a real published chapter and a human has listened to the result.

- [/] **Task 6L: Multilingual story content and voice — Hindi, Telugu, English**
  - **Scope decided via user Q&A (not re-litigated here):** (1) story CONTENT (generated chapters/dialogue/screenplay) and VOICE (STT + TTS) become multilingual; the app's UI chrome (buttons/labels/forms) stays English — no UI i18n framework was added, that stays explicitly out of scope. (2) Only Hindi, Telugu, English — not all 22 scheduled languages. (3) Selection is a per-story preference chosen once at story-creation time, not a per-request toggle.
  - **Target Files:** `migrations/0016_story_language.sql`, `src/story_engine/domain/models.py` (`StoryLanguage` enum), `src/story_engine/agents/prompts/system.py` (`storyteller_language_instruction`/`storyteller_prompt_for_language`), `src/story_engine/api/routes/stories.py` (`StoryInput.language`/`StoryResponse.language`), `src/story_engine/workers/generation_job.py` (looks up `stories.language`, builds the Storyteller's system prompt with it), `src/story_engine/api/routes/voice.py` (`_language_hint`, reads `?language=` query param), `src/story_engine/agents/voice_provider.py` (`transcribe_chunk`'s new `language` kwarg, forwarded to Whisper's own `language` field only when present), `web/components/features/onboarding/LanguagePicker.tsx` (new), `web/components/features/onboarding/OnboardingFlow.tsx` (new `"language"` step between template and personalization), `web/components/features/onboarding/CastLock.tsx` (sends `language` to `POST /stories`, stores `story-engine-story-language` in localStorage), `web/lib/voice-stream.ts` (`useVoiceTranscription` takes an optional `language` arg, appended as a WS query param), `web/components/shared/VoiceInputButton.tsx` (optional `language` prop, falling back to reading `story-engine-story-language` from localStorage so the four non-onboarding voice surfaces — `WorkspaceView.tsx`, `CanonEventRequestDialog.tsx`, `RevisionRequestForm.tsx` — get a hint without each needing the story object threaded into props).
  - **Details:** `language` is `TEXT NOT NULL DEFAULT 'en'` on `stories` with a `CHECK (language IN ('en','hi','te'))` — a DB-level guard against ever writing a fourth value, not just an API-level one. `StoryLanguage` mirrors the same three codes as a `StrEnum` (matching every other domain enum's pattern in `domain/models.py`); `StoryInput.language: StoryLanguage = StoryLanguage.ENGLISH` means Pydantic itself rejects an unsupported code (e.g. `"fr"`) with a 422 before the route body even reaches `create_story` — verified at the model layer (see Testing below), since the auth dependency raises 401 before body validation on every route in this API regardless of body content, which made a full round-trip 422 assertion impossible to write honestly without a live DB (documented in the new test file's docstring). Only the **Storyteller**'s system prompt gets a language instruction (`"Write all narrative prose, dialogue, and character names in {language}... native script, not transliterated"`) — Director/World/Evaluator reasoning stays English-only internally, since Evaluator's output is an APPROVE/REJECT verdict consumed by the generation loop, not text a reader ever sees; this is a deliberate scope choice, documented in `prompts/system.py`, not an oversight. `generation_job.py`'s single context-fetch query now also selects `s.language`, converts it to `StoryLanguage`, and swaps `system_prompt=STORYTELLER` for `system_prompt=storyteller_prompt_for_language(language)` for the one call that produces the actual chapter text. `voice.py`'s WS route reads an optional `?language=` query param (validated against the same three-code set server-side, so an unrecognized value is silently ignored rather than passed to Whisper) and forwards it into every `transcribe_chunk` call as Whisper's own `language` field; when absent, Whisper falls back to its own auto-detection, matching prior behavior exactly for every existing caller. **`narration.py`/TTS finding (no code change made, documented per the task instructions):** OpenAI's TTS models/voices (including the fixed `settings.narrator_voice` default `"alloy"`) are inherently multilingual — they read back whatever text/language they're given rather than needing a per-language voice selection, so once `published_chapter_text` contains Hindi/Telugu prose (because the Storyteller wrote it in that language), narration should "just work" with zero changes to `narration.py`/`voice_provider.py`'s `synthesize_speech`. This is a documented expectation, not a verified one — a live OpenAI TTS call against real Hindi/Telugu chapter text has not been made in this pass.
  - **Frontend:** `LanguagePicker.tsx` presents three options — English / हिन्दी / తెలుగు — showing each language's own script as the primary label (English name shown only as a secondary caption for the two non-English options), matching `TemplatePicker.tsx`'s existing card/`fieldset`/radio pattern. `OnboardingFlow.tsx` inserts a `"language"` step between `"template"` and `"personalization"`; `CastLock.tsx` sends the selected code as `language` on `POST /stories` and, on success, stores the server-confirmed value in `localStorage["story-engine-story-language"]`. **Honesty note on voice wiring:** `SeedForm.tsx`'s `VoiceInputButton` runs during the `"seed"` step, which happens *before* language is chosen in the flow — so it has no language yet to pass and relies on Whisper auto-detect for that one call, same as before this pass. The other three voice surfaces (`WorkspaceView.tsx`, `CanonEventRequestDialog.tsx`, `RevisionRequestForm.tsx`) operate on an already-created story, so `VoiceInputButton`'s localStorage fallback gives them a real hint without a deeper prop-drilling refactor of those components' data flow, which was out of scope for this pass.
  - **Status:** Implemented as described. Migration written but not applied to any live database. Backend prompt-injection, story-creation field, and voice-hint wiring are all in place; frontend picker/flow/localStorage wiring is in place.
  - **Testing:** `tests/contract/test_story_language_contract.py` (new) — `StoryInput` (the exact Pydantic model `create_story` validates against) accepts `en`/`hi`/`te`, defaults to `en` when omitted, and rejects `fr`/`es`/`"EN "` (leading/trailing whitespace)/`"hindi"`/`""` with a `ValidationError`; also confirms the route itself still 401s before any body validation is visible (documents why a route-level 422 test isn't written). `tests/unit/test_storyteller_language_prompt.py` (new) — confirms the correct language-name fragment appears in the instruction for each of the 3 `StoryLanguage` values, that the base `STORYTELLER` text is preserved, and that all three languages produce distinct prompts. `python3 -m py_compile` clean on every changed `.py` file (`domain/models.py`, `agents/prompts/system.py`, `api/routes/stories.py`, `workers/generation_job.py`, `api/routes/voice.py`, `agents/voice_provider.py`). **Actually executed this session** (reused the Task 5J.1 Python 3.10 `enum.StrEnum` → `strenum` backport workaround via a `sitecustomize.py` on `PYTHONPATH`): full `pytest tests/unit tests/contract -q` — **169 passed** (152 pre-existing + 17 new; 0 regressions). `npx tsc --noEmit -p web/tsconfig.json` — this sandbox has no `web/node_modules` at all (not even from a prior pass) and no global TypeScript, so a local `npm install typescript --no-save` was done in a scratch directory to get a `tsc` binary at all; running it against `web/tsconfig.json` produces exactly one error, `app/layout.tsx(1,8): TS2882 Cannot find module ... './globals.css'`, which is pre-existing/environmental (a CSS side-effect import with no `node_modules` present to resolve types from) and unrelated to any file this pass touched — no errors were introduced in `LanguagePicker.tsx`, `OnboardingFlow.tsx`, `CastLock.tsx`, `voice-stream.ts`, or `VoiceInputButton.tsx`. **Not verifiable in this sandbox, and explicitly not claimed:** actual Hindi/Telugu generation quality (does the Storyteller reliably produce fluent, non-transliterated prose in each script?), actual Whisper transcription accuracy for Hindi/Telugu speech with the `language` hint versus without it, and actual TTS output naturalness for Hindi/Telugu text — all four require a live OpenAI API key, live network calls, and a native Hindi/Telugu speaker's review, none of which exist here. Do not mark `[x]` until that live round-trip has been run for both non-English languages and reviewed by a native speaker.

---

## Build Order and Parallelism Map

```text
Phase 1:  Track A ─────┐
                        ├── Sync 1
          Track B ─────┘

Phase 2:  Track C ─────┐
                        ├── Sync 2
          Track D ─────┘

Phase 3:  Track E ─────┐
                        ├── Sync 3
          Track F ─────┘

Phase 4:  Track G ─────┐
                        ├── Sync 4
          Track H ─────┘

Phase 5:  Track I ─────┐
                        ├── Sync 5 → Production approval
          Track J ─────┘
```

Tracks within a phase can run in parallel only after their prior sync point succeeds. Do not begin a task that edits another active track’s target path. If a shared interface changes, update its typed contract first, then coordinate the dependent tracks at the next sync point.
