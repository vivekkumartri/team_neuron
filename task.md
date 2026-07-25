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

*Target isolation: repository root, `resources/` except `resources/lakebase.yml`, `.github/`, `docs/adr/`, and `scripts/check_task_paths.py` only.*

- [x] **Task 1A.1: Initialize the Git repository and dependency manifests**
  - **Tooling:** GitHub, Python 3.11+, Node.js, uv/pip, npm/pnpm.
  - **Target Files:** `.gitignore`, `pyproject.toml`, `package.json`, `README.md`.
  - **Details:** Create one repository containing the Python application/wheel and Next.js web client. Pin Python and Node versions. Ignore `.env*`, build outputs, local certificates, Databricks CLI profiles, and generated static assets.
  - **Verification:** `git status --ignored`; `python -m pip install -e '.[dev]'`; `npm ci`; `npm run typecheck`.

- [/] **Task 1A.2: Create the Declarative Automation Bundle skeleton**
  - **Tooling:** Databricks CLI, Declarative Automation Bundles.
  - **Target Files:** `databricks.yml`, `resources/variables.yml`, `resources/app.yml`, `resources/jobs.yml`, `resources/permissions.yml`.
  - **Details:** Define `dev`, `staging`, and `prod` targets. Parameterize workspace host, catalog, schema, Lakebase project/database, app name, service principal, and UC Volume. Do not create or edit `resources/lakebase.yml`; Task 1B.2 is its sole owner. Do not hard-code workspace IDs or credentials.
  - **Verification:** `databricks bundle validate -t dev` returns success; `databricks bundle summary -t dev` lists the expected resource definitions.

- [/] **Task 1A.3: Define deployment identity and least-privilege permission design**
  - **Tooling:** Databricks IAM, Unity Catalog, Lakebase roles, Databricks Apps service principal.
  - **Target Files:** `resources/permissions.yml`, `docs/adr/001-deployment-identities.md`.
  - **Details:** Define separate identities/roles for app runtime, job runtime, CI deployer, migration runner, and administrator. Document the intended catalog/schema/volume/database privileges and who can deploy to each target. Apply database roles only after Task 1B.2 has provisioned Lakebase.
  - **Verification:** ADR is reviewed and lists no owner credential for any runtime identity. The executable permission-negative checks are deferred to Task 2C.5 after tables and policies exist.

- [/] **Task 1A.4: Build CI and protected deployment workflows**
  - **Tooling:** GitHub Actions, Databricks CLI.
  - **Target Files:** `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`.
  - **Details:** CI runs Python/TypeScript lint, type checks, unit tests, secret scan, bundle validation, and—once Track H exists—a Playwright accessibility/navigation smoke subset on every pull request. Deploy workflow requires reviewed main-branch changes, deploys `dev`, runs integration tests, and uses an approval gate for `staging`/`prod`.
  - **Verification:** Open a test pull request and confirm CI fails on a deliberately failing unit test and an axe-core violation after the Track H suite is available; run `workflow_dispatch` to deploy `dev` successfully.

- [x] **Task 1A.5: Add source-traceability and parallel-path validation**
  - **Tooling:** Python or Node.js, GitHub Actions.
  - **Target Files:** `requirements-reconciliation.md`, `scripts/check_task_paths.py`, `.github/workflows/ci.yml`.
  - **Details:** Commit the source-reconciliation appendix. Add a CI check that parses `task.md` target-file declarations and flags collisions between tracks marked parallel, plus a check that required reconciliation terms remain present.
  - **Verification:** A fixture with a deliberately duplicated concurrent-track path fails CI; the current task plan passes; CI confirms the explicit prototype supersession entries exist.

### Track B — Databricks Data and Application Prerequisites

*Target isolation: `resources/lakebase.yml`, `notebooks/00_platform_setup.py`, `notebooks/01_lakebase_smoke_test.py`, `notebooks/02_audit_delta_smoke_test.py`, `content/`, `docs/runbooks/`, and `docs/adr/003-template-rights.md` only.*

- [ ] **Task 1B.1: Provision Unity Catalog data boundaries**
  - **Tooling:** Unity Catalog, SQL Warehouse or notebook.
  - **Target Files:** `notebooks/00_platform_setup.py`, `docs/runbooks/platform-bootstrap.md`.
  - **Details:** Create environment-specific catalog/schema naming conventions and a managed UC Volume for approved artifacts. Create the Delta audit table namespace. Keep transactional request data in Lakebase, not Delta.
  - **Verification:** Execute the notebook; `SHOW SCHEMAS IN <catalog>` and `dbutils.fs.ls('/Volumes/<catalog>/<schema>/<volume>')` show the expected resources.

- [ ] **Task 1B.2: Provision Lakebase Postgres and baseline roles**
  - **Tooling:** Lakebase, PostgreSQL migrations.
  - **Target Files:** `resources/lakebase.yml`, `migrations/0001_bootstrap.sql`, `notebooks/01_lakebase_smoke_test.py`.
  - **Details:** Create separate Lakebase branches/databases for `dev`, `staging`, and `prod`; configure the App and Job resource bindings. Create non-owner application roles. Add extensions required for UUIDs and row-level security.
  - **Verification:** App/job identities connect using injected resource configuration; the smoke notebook executes `SELECT current_user, current_database()` and confirms it is not using the owner role.

- [ ] **Task 1B.3: Create the redacted Delta audit sink**
  - **Tooling:** PySpark, Delta Lake, Unity Catalog.
  - **Target Files:** `src/story_engine/analytics/audit_export.py`, `notebooks/02_audit_delta_smoke_test.py`.
  - **Details:** Create append-only Delta tables for redacted generation lifecycle metrics, latency, status, retry count, and tenant-hashed identifier. Explicitly exclude prose, hidden characteristics, user preferences, prompts, and raw agent payloads.
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

- [ ] **Task 2C.1: Create tenant, story, personalization schema, and migration runner**
  - **Tooling:** PostgreSQL/Lakebase, Alembic or SQL migration runner.
  - **Target Files:** `migrations/0002_tenants_profiles_stories.sql`, `scripts/migrate.py`, `src/story_engine/persistence/models.py`, `tests/integration/persistence/test_tenants.py`.
  - **Details:** Implement `users`, `user_preferences`, immutable `personalization_snapshots`, `stories`, `arcs`, and configuration flags. Include `user_id`, preference source/consent, soft delete, snapshot version, and per-story personalization enablement. Add an idempotent migration runner that uses the dedicated migration identity, records applied versions/checksums, and refuses drift.
  - **Verification:** Migration applies to an empty database and a second execution is a no-op; tests prove a snapshot cannot be created from another user’s preference and a disabled story cannot select a snapshot.

- [ ] **Task 2C.2: Create branch-safe narrative, template, trait-state, and world-state schema**
  - **Tooling:** PostgreSQL/Lakebase.
  - **Target Files:** `migrations/0003_branches_world_state.sql`, `src/story_engine/persistence/branches.py`, `tests/integration/persistence/test_branch_isolation.py`.
  - **Details:** Create original/licensed templates with source-license, approved-scene-map, sponsorship/disclosure metadata; branches, chapters, branch entity state, immutable versioned `character_trait_states`, branch relationships, branch canon facts, world snapshots, choices, scenes, dialogue, revisions, canon events, and ending-option records. Record the focal character and trait-state version used by every chapter. Enforce one current-state source per branch and unique chapter indexes per branch.
  - **Verification:** Integration test forks a parent branch, changes a child entity location/trait state, and asserts the parent/sibling states remain unchanged and the historical chapter resolves its original trait version.

- [ ] **Task 2C.3: Create isolated character and Director memory schema**
  - **Tooling:** PostgreSQL/Lakebase.
  - **Target Files:** `migrations/0004_memory_and_director.sql`, `src/story_engine/persistence/memory.py`, `tests/integration/persistence/test_memory_cutoffs.py`.
  - **Details:** Create branch-aware character core/episodic/screenplay memory, one `story_director` per branch, Director strategy/decision/open-thread memory, and ancestry cutoffs. Core profile is immutable for founding cast after lock; Director memory rejects private character fields.
  - **Verification:** Test that a child branch reads inherited memory only through its fork chapter, cannot see future parent entries, and Director-memory insertion rejects a hidden-characteristic field.

- [ ] **Task 2C.4: Create durable job, event, staging, and report schema**
  - **Tooling:** PostgreSQL/Lakebase.
  - **Target Files:** `migrations/0005_jobs_events_reports.sql`, `src/story_engine/persistence/jobs.py`, `tests/integration/persistence/test_job_idempotency.py`.
  - **Details:** Create generation jobs/events, leases, attempts, candidate staging rows, outbox, agent runs, evaluator/business reports, and retry metadata. Enforce a single active job per branch and idempotency-key uniqueness.
  - **Verification:** Two submissions with one idempotency key return the same job; a second active job on the branch is rejected; candidate rows are inaccessible from published chapter queries.

- [ ] **Task 2C.5: Enforce RLS, tenant context, and canonical write authority**
  - **Tooling:** PostgreSQL RLS, stored procedures/functions.
  - **Target Files:** `migrations/0006_rls_and_roles.sql`, `src/story_engine/persistence/tenant_context.py`, `tests/integration/persistence/test_rls.py`.
  - **Details:** Enable RLS for every user-owned table. Set tenant context via parameterized transaction-local `set_config`; expose world commits only through a narrowly privileged database function/service role. Do not grant canonical table write access to API, Director, storyteller, evaluator, or business roles.
  - **Verification:** Negative tests prove user A cannot read/write user B rows, worker roles cannot update canonical tables directly, and world-command transaction can commit an allowed state change.

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

- [ ] **Task 3E.3: Implement candidate generation and pre-publication evaluation**
  - **Tooling:** Python, pytest.
  - **Target Files:** `src/story_engine/services/generation_pipeline.py`, `src/story_engine/services/candidate_service.py`, `tests/unit/agents/test_generation_pipeline.py`.
  - **Details:** Implement bounded Director/world discussion, candidate staging, evaluator outcome, automatic regeneration after major divergence, and final world-command commit. Generate a configurable approximately-30-second chapter unit centered on the selected focal character; candidate output must be visibly unpublished until commit and pass policy gates before evaluation.
  - **Verification:** Tests cover focal-character context, configured chapter-length range, approval, rejection/revision, retry exhaustion, single-character failure, policy block, and no published scene/canon row after an unapproved candidate.

- [ ] **Task 3E.4: Implement progression, trait-state, rewind, canon-event, ending, and revision workflows**
  - **Tooling:** Python, pytest.
  - **Target Files:** `src/story_engine/services/progression.py`, `src/story_engine/services/trait_states.py`, `src/story_engine/services/canon_events.py`, `src/story_engine/services/endings.py`, `src/story_engine/services/revisions.py`, `tests/unit/agents/test_canon_events.py`.
  - **Details:** Implement exactly three progression modes: Continue (same branch), Edit traits (suggested/freeform/go-with-flow; validated child branch when changed), and Jump/rewind (selected prior scene; child branch). Implement focal-character selection, versioned trait/relationship state, ending eligibility/manual request, multiple ending options, and revisions. On character introduction, world agent returns relationship suggestions for explicit author confirmation. Approved screenplay edits create replacement child branches rather than mutating published chapters.
  - **Verification:** Test all three modes, trait-state visibility/versioning, rewind from any published scene, the persisted ending-readiness formula/components and manual threshold, multiple endings, kill/revive/move/introduce/revision flows, and an event arriving during generation being queued/rejected without altering a stale candidate.

### Track F — Job Worker and Operational Export

*Target isolation: `src/story_engine/workers/`, `src/story_engine/analytics/`, `resources/jobs.yml`, and `tests/integration/workers/` only.*

- [ ] **Task 3F.1: Package the Python worker as a wheel and create job entry points**
  - **Tooling:** Python packaging, Databricks Jobs.
  - **Target Files:** `pyproject.toml`, `src/story_engine/workers/generation_job.py`, `src/story_engine/workers/report_job.py`, `resources/jobs.yml`.
  - **Details:** Define wheel tasks for generation, evaluator/business reports, memory compaction, and audit export. Pass only `job_id`/tenant-safe identifiers as parameters; load secrets/resources through Databricks runtime bindings.
  - **Verification:** Build wheel; `databricks bundle deploy -t dev`; run the generation job with a seeded job ID and inspect successful task output.

- [ ] **Task 3F.2: Implement queue lease, retry, outbox, job dispatch, and stale-version handling**
  - **Tooling:** Lakebase Postgres, Python, pytest.
  - **Target Files:** `src/story_engine/workers/queue.py`, `src/story_engine/workers/outbox.py`, `src/story_engine/services/job_dispatcher.py`, `tests/integration/workers/test_queue.py`.
  - **Details:** Claim jobs with transactional leases, use retry/backoff, enforce branch lock/version checks, emit ordered events, and safely recover expired leases. Implement the one job-dispatcher service used by the API: it reads committed outbox rows and invokes the configured Databricks Job with only `job_id`; a failed launch remains retryable in the outbox.
  - **Verification:** Simulate worker crash after lease; a second worker recovers exactly once; duplicate outbox delivery does not create duplicate chapters/events; failed Databricks Job launch is retried from the outbox without recreating the Lakebase job row.

- [ ] **Task 3F.3: Export redacted operational audit data to Delta**
  - **Tooling:** PySpark, Delta Lake, Unity Catalog.
  - **Target Files:** `src/story_engine/analytics/export_generation_audit.py`, `src/story_engine/analytics/audit_schema.py`, `tests/integration/workers/test_audit_export.py`.
  - **Details:** Incrementally export completed job metadata using a durable high-water mark. Write only the approved redacted audit schema to UC Delta and create a reconciliation report.
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

- [ ] **Task 4G.1: Create the Databricks App runtime and SPA static web serving**
  - **Tooling:** Databricks Apps, FastAPI, Uvicorn, Next.js static export.
  - **Target Files:** `app.yaml`, `scripts/build_web.sh`, `src/story_engine/app.py`, `src/story_engine/api/static.py`, `resources/app.yml`.
  - **Details:** Define the App entry point, health/readiness endpoints, resource bindings, static asset directory, and production security headers. Build the Next.js client before App packaging, serve its static export, and return the SPA shell for non-`/api/*` client routes. Do not store credentials in `app.yaml`; use Lakebase/App resource injection.
  - **Verification:** Deploy App to `dev`; App URL returns health `200`, serves the placeholder SPA shell before Track H is complete, resolves a client-side deep link to the shell, and fails readiness when the database binding is intentionally unavailable.

- [ ] **Task 4G.2: Implement authenticated REST APIs**
  - **Tooling:** FastAPI, Pydantic, Lakebase.
  - **Target Files:** `src/story_engine/api/auth.py`, `src/story_engine/api/routes/stories.py`, `branches.py`, `chapters.py`, `world.py`, `preferences.py`, `traces.py`, `tests/contract/test_rest_contract.py`.
  - **Details:** Implement the APIs in `design.md`, including Databricks App identity validation, just-in-time user provisioning on the first authenticated request, idempotency headers, ETags/version conflicts, authorization, personalization snapshots, canon-event requests, job-dispatch submission, and trace flag controls. Use API DTOs that exclude private data by construction.
  - **Verification:** Contract tests validate JIT user creation is idempotent, success/error schemas, `401/403/404/409/429` behavior, cross-tenant denial, idempotent replay, and hidden-characteristic redaction.

- [ ] **Task 4G.3: Implement SSE generation activity endpoint**
  - **Tooling:** FastAPI SSE, Lakebase event queries.
  - **Target Files:** `src/story_engine/api/routes/events.py`, `src/story_engine/api/sse.py`, `tests/contract/test_sse.py`.
  - **Details:** Stream ordered, redacted `generation_events` with `id`, reconnect via `Last-Event-ID`, heartbeat, authorization recheck, and bounded polling. Never emit raw provider tokens or unpublished private context.
  - **Verification:** Integration test disconnects/reconnects after event 3 and receives events 4+ exactly once; a different user receives no stream or job metadata.

### Track H — Next.js Client and Accessibility

*Target isolation: `web/`, `tests/e2e/`, and front-end config files only.*

> **Prototype boundary:** `StoryEngineProto.jsx` is a visual reference for typography, color, and card layout only. Its hidden-trait row, hard 20-character gate, direct Sandbox mutation handlers, two-choice progression interaction, and fully operable Comic Studio/export controls are pre-redesign behavior and must not be reused. In this text MVP, Comic/Export controls render only as non-operable **Coming later** states.

- [ ] **Task 4H.1: Build the static-export application shell and authenticated navigation**
  - **Tooling:** Next.js, React, TypeScript, Tailwind CSS, Playwright, axe-core.
  - **Target Files:** `web/app/layout.tsx`, `web/app/page.tsx`, `web/components/app-shell/`, `web/lib/api-client.ts`, `web/lib/client-router.ts`, `tests/e2e/navigation.spec.ts`, `tests/e2e/accessibility.spec.ts`.
  - **Details:** Build a Next.js static-export shell with a client-side route table, rather than runtime Next dynamic routes. FastAPI always serves the SPA shell for approved client paths. Build desktop-first sidebar, responsive mobile drawer, protected routes, story/branch context, error boundaries, user preference entry point, and accessibility preferences.
  - **Verification:** Playwright verifies keyboard navigation, mobile drawer, unauthenticated redirect, and a 200% zoom screenshot with no hidden primary action. axe-core scan passes WCAG AA color-contrast and critical accessibility checks for default, high-contrast, and increased-text themes.

- [ ] **Task 4H.2: Build seed clarification, template, concept, cast, and personalization feature views**
  - **Tooling:** React Hook Form/Zod or equivalent, Tailwind CSS, Playwright.
  - **Target Files:** `web/components/features/onboarding/`, `web/components/features/preferences/`, `web/lib/routes.ts`, `tests/e2e/onboarding.spec.ts`.
  - **Details:** Implement no-hard-minimum seed validation, visible clarification/redirect loop, original/licensed template picker with disclosure labels, consented personalization selection, family-tree summary, cast lock confirmation, and immediate Chapter 1 launch. Hidden-characteristic UI must not exist; do not port the prototype `>=20` gate or blurred hidden row.
  - **Verification:** E2E flow submits a short seed, completes clarification, selects a disclosed template or custom concept, confirms a preference snapshot, locks cast, and navigates to a queued generation workspace; DOM/text scan explicitly rejects the retired `hidden-row`, “secret exists”, “minimum 20 characters”, and blurred-hint patterns.

- [ ] **Task 4H.3: Build workspace feature view, streamed agent activity, trait cards, and branch controls**
  - **Tooling:** React, SSE client, TanStack Query, Tailwind CSS, Playwright.
  - **Target Files:** `web/components/features/workspace/`, `web/components/workspace/`, `web/lib/generation-stream.ts`, `tests/e2e/generation.spec.ts`.
  - **Details:** Render loader → live activity → unpublished candidate preview → published chapter. Implement reconnect, jump-to-latest, reduced motion, accessible entity list, read-only graph, visible versioned trait cards, focal-character selector, and exactly three progression modes: Continue automatically, Edit traits, Jump/rewind.
  - **Verification:** Mocked SSE E2E test checks ordered cards, reconnect behavior, no raw secret text, published-state gating, trait update visibility before generation, all three progression modes, and a second branch that does not alter the parent view.

- [ ] **Task 4H.4: Build world, ending, reports, revision, and recovery feature views**
  - **Tooling:** React, Playwright.
  - **Target Files:** `web/components/features/world/`, `web/components/features/endings/`, `web/components/features/reports/`, `web/components/canon-events/`, `web/components/revisions/`, `tests/e2e/recovery.spec.ts`.
  - **Details:** Implement canon-event/relationship request dialogs, evaluator/business reports, ending-options request/selection, trace drawer behind feature flag, blocked-generation retry, archive/unarchive, and Edit-as-revision flow. Never reuse the prototype’s direct kill/revive handlers: show target, branch, permanent-record consequence, explicit confirmation, then pending/evaluating status before any entity state changes. Show policy blocks, quota state, and safe alternative copy clearly.
  - **Verification:** E2E test requests a move/relationship event and a kill event, confirms no state changes before evaluator/world decision, receives the final decision, requests ending options at the threshold, simulates blocked generation, retries it, and confirms a revision creates a replacement branch instead of changing the original chapter.

### 🛑 SYNC POINT 4: App Integration on Databricks 🛑

- [ ] **Task 4.S1: Deploy the App and complete browser-level smoke tests**
  - **Target Files:** all Phase 4 files only.
  - **Details:** Build static web assets, package the App, deploy through the bundle, and run Playwright against the `dev` App URL with test identities.
  - **Verification:** Health/readiness/API/SSE tests pass; the Chapter 1 test reaches `PUBLISHED`; cross-tenant and hidden-secret negative browser tests pass.

---

## Phase 5: Observability, Quality, and Release Readiness

### Track I — Monitoring, Data Quality, and Runbooks

*Target isolation: `src/story_engine/analytics/`, `docs/runbooks/`, and `tests/integration/observability/` only. Track I does not create ADRs in this phase.*

- [ ] **Task 5I.1: Implement application metrics and structured logging**
  - **Tooling:** Python logging/OpenTelemetry-compatible exporter, Databricks logs, Delta audit.
  - **Target Files:** `src/story_engine/analytics/observability.py`, `docs/runbooks/observability.md`, `tests/integration/observability/test_metrics.py`.
  - **Details:** Record job queue latency, agent latency, retry count, evaluator outcome, SSE reconnect count, RLS denial count, deployment version, per-job/story/user model-token and spend estimate, cost-budget threshold events, chapter-loop completion, branch usage, trait-edit acceptance, ending-option use, and future comic-export placeholders. Use correlation IDs; redact payloads by default. Define a configurable per-user budget kill switch that pauses new generation submissions with a clear message.
  - **Verification:** A test job produces one correlated log/metric chain; log scanner finds no prompt, secret, hidden characteristic, or user preference value; an over-budget fixture emits the budget event and rejects only new submissions.

- [ ] **Task 5I.2: Add data-quality and reconciliation checks**
  - **Tooling:** PySpark, SQL, pytest.
  - **Target Files:** `src/story_engine/analytics/quality_checks.py`, `notebooks/03_operational_quality_checks.py`, `tests/integration/observability/test_reconciliation.py`.
  - **Details:** Check published chapter/state consistency, branch ancestry validity, event sequence continuity, audit-export reconciliation, and forbidden Delta columns. Run checks as a scheduled Databricks Job.
  - **Verification:** Inject a known broken fixture; check fails with an actionable identifier. Clean fixture passes and job status is `Succeeded`.

- [ ] **Task 5I.3: Write operational incident and recovery runbooks**
  - **Tooling:** Markdown, Databricks Jobs/App/Lakebase procedures.
  - **Target Files:** `docs/runbooks/generation-failure.md`, `tenant-isolation-incident.md`, `rollback.md`, `access-revocation.md`.
  - **Details:** Document response for stuck lease, failed bundle deploy, stale candidate, secret-redaction failure, RLS incident, Lakebase outage, user preference deletion, and app rollback. Include commands with placeholders only.
  - **Verification:** A reviewer follows the generation-failure drill in `dev` and restores a stuck test job without modifying published canon.

### Track J — Performance, Security, and Release Gates

*Target isolation: `tests/performance/`, `tests/security/`, `.github/workflows/`, and `docs/adr/2xx-*` only.*

- [ ] **Task 5J.1: Execute security, safety, IP, and privacy test suite**
  - **Tooling:** pytest, Playwright, secret scanner, dependency scanner.
  - **Target Files:** `tests/security/test_rls_negative.py`, `test_prompt_injection.py`, `test_event_redaction.py`, `test_personalization_isolation.py`, `test_content_ip_wellbeing.py`.
  - **Details:** Test every stated loophole guard: tenant crossing, hidden-secret stream leak, prompt injection, Director-memory privacy, stale writes, duplicate branches, unauthorized personalization snapshot use, blocked safety categories, copyrighted-IP handling, sensitive-content privacy, disclosed template/sponsorship behavior, and explicit quota responses.
  - **Verification:** All security/policy tests pass; secret/dependency scan has no unapproved findings; evidence is attached to the release pull request.

- [ ] **Task 5J.2: Execute performance and resilience tests**
  - **Tooling:** k6/Locust, pytest, Databricks Jobs.
  - **Target Files:** `tests/performance/api_load.js`, `tests/performance/sse_reconnect.js`, `docs/adr/201-slo-and-capacity.md`.
  - **Details:** Establish explicit dev/staging SLOs for API latency, event delivery, job queue start, and generation completion. Test concurrent users, reconnect storms, rate limits, job worker restart, and Lakebase connection recovery.
  - **Verification:** Test report meets documented SLO thresholds or creates approved remediation tasks; no duplicate canon commits occur under retry/load.

- [ ] **Task 5J.3: Define production release checklist and rollback gate**
  - **Tooling:** GitHub Environments, Declarative Automation Bundles, Databricks Apps/Jobs.
  - **Target Files:** `docs/runbooks/release-checklist.md`, `.github/workflows/deploy.yml`.
  - **Details:** Require migration backup/restore validation, bundle validation, staged deploy, App health check, worker job run, RLS negative test, audit quality check, and approval before production. Rollback must be application/bundle version rollback; never delete published canon as a rollback mechanism.
  - **Verification:** Perform a staging release rehearsal and rollback rehearsal; capture deployed bundle version and successful restoration evidence.

### 🛑 SYNC POINT 5: Production Readiness Review 🛑

- [ ] **Task 5.S1: Sign off the release evidence pack**
  - **Target Files:** `docs/runbooks/release-checklist.md` and generated CI artifacts only.
  - **Details:** Review all phase gates, test reports, security evidence, deployment manifests, migration status, actual quota defaults, model budget thresholds, and known risks. Create follow-up tasks for intentionally deferred image/comic generation, animated portraits, collaboration, and vector retrieval.
  - **Verification:** All required checkboxes are complete, `databricks bundle validate -t prod` succeeds, and the release approver records the commit SHA and bundle version.

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
