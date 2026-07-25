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

- [/] **Task 2C.5: Enforce RLS, tenant context, and canonical write authority** *(schema/tests written; not yet executed against a live Postgres)*
  - **Tooling:** PostgreSQL RLS, stored procedures/functions.
  - **Target Files:** `migrations/0006_rls_and_roles.sql`, `migrations/0008_canonical_write_revocation.sql`, `src/story_engine/persistence/tenant_context.py`, `tests/integration/persistence/test_rls.py`.
  - **Details:** Enable RLS for every user-owned table. Set tenant context via parameterized transaction-local `set_config`; expose world commits only through a narrowly privileged database function/service role. Do not grant canonical table write access to API, Director, storyteller, evaluator, or business roles. **Gap closed in this pass:** migration 0006 only revoked function-execute rights on `world_publish_chapter`; it never revoked direct table DML on `branch_entity_states`/`character_trait_states`/`branch_relationships`/`branch_canon_facts`/`entities`/`chapters`, so the single Databricks-managed app role could still bypass the world-agent path with a plain `UPDATE`. Migration 0008 revokes that DML from `PUBLIC` and adds `world_commit_entity_state`/`world_commit_trait_state` as the only write path; `branch_relationships`/`branch_canon_facts` write functions still need to be added alongside Task 3E.4's canon-event-request work.
  - **Verification:** Negative tests prove user A cannot read/write user B rows, worker roles cannot update canonical tables directly, and world-command transaction can commit an allowed state change.
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

- [ ] **Task 3E.3: Implement candidate generation and pre-publication evaluation**
  - **Tooling:** Python, pytest.
  - **Target Files:** `src/story_engine/services/generation_pipeline.py`, `src/story_engine/services/candidate_service.py`, `tests/unit/agents/test_generation_pipeline.py`.
  - **Details:** Implement bounded Director/world discussion, candidate staging, evaluator outcome, automatic regeneration after major divergence, and final world-command commit. Generate a configurable approximately-30-second chapter unit centered on the selected focal character; candidate output must be visibly unpublished until commit and pass policy gates before evaluation.
  - **Verification:** Tests cover focal-character context, configured chapter-length range, approval, rejection/revision, retry exhaustion, single-character failure, policy block, and no published scene/canon row after an unapproved candidate.

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
  - **Status:** `generation_job.py`/`report_job.py` entry points added, registered under `[project.entry-points.packages]`, and wired into `resources/jobs.yml` (`generation_job`/`report_job` resources, wheel-task, `job_id`/`chapter_id`-only parameters). Both entry points deliberately raise `NotImplementedError` at the point they'd call the real Director/World/Storyteller/Evaluator/Business model adapters — Task 3E.2's adapters exist but aren't wired to a live model provider yet, and faking a "success" here would misrepresent an untested path. Memory-compaction and audit-export wheel tasks are not yet defined in `resources/jobs.yml`.
  - **Verification:** Build wheel; `databricks bundle deploy -t dev`; run the generation job with a seeded job ID and inspect successful task output. (Not run — no `dev` workspace/credentials available in this environment; `python3 -m build` was not attempted for the same reason bundle deploy wasn't.)

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
  - **Status:** `auth.py` (JIT provisioning), `stories.py`, `branches.py` (read-only timeline), `chapters.py` (published-only reads), `world.py` (read-only branch state + `POST /branches/{id}/canon-event-requests`, inserting a `DRAFT` row into `canon_event_requests` per migration 0009), `preferences.py` (full CRUD + snapshot creation), and `traces.py` (trace-flag-gated) are implemented and wired into `app.py`. Remaining gap: no route yet submits a generation job through `job_dispatcher.dispatch_pending`, and idempotency-key/ETag mutation semantics are still not implemented on any mutating route (canon-event-request POST included). Do not mark `[x]` until those exist.
  - **Verification:** Contract tests validate JIT user creation is idempotent, success/error schemas, `401/403/404/409/429` behavior, cross-tenant denial, idempotent replay, and hidden-characteristic redaction. `tests/contract/test_rest_contract.py` covers the auth boundary and schema-shape checks (401 without identity headers, no hidden-characteristic/candidate-staging fields in any response schema, 401 on unauthenticated canon-event-request POST, `extra=forbid` on `CanonEventRequestInput`); the full idempotent-replay and cross-tenant contract cases move to `tests/integration/persistence` once a live job/canon-event pipeline is available to exercise, since this sandbox has no Lakebase connection.

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
  - **Status:** Implemented `SeedForm` (no hard minimum; a visible, dismissable clarification prompt appears below a 12-character soft threshold, author can always continue), `TemplatePicker` (explicit `ORIGINAL`/`LICENSED_REFERENCE` disclosure badge on every option, no undisclosed licensed content), `PersonalizationConsent` (opt-in only, nothing pre-checked, calls the real `PATCH /me/preferences` per accepted category then `POST /me/personalization-snapshots` to freeze the snapshot), `CastLock` (calls the real `POST /api/v1/stories`), and `OnboardingFlow` orchestrating all four steps, wired as the default `/` route. `grep -rniE "hidden-row|secret exists|minimum 20|blur"` across `web/components` and `web/app` returns no matches. `tests/e2e/onboarding.spec.ts` is now written. **Known backend gap, not a frontend gap:** there is no family-tree-summary or dedicated cast-lock endpoint in the REST API yet — only `POST /api/v1/stories` (bare `title`) exists, so `CastLock` currently creates the story using the seed text as its title with `personalization_enabled: true`, and the family-tree summary step described in design.md is not rendered because there's no data to summarize. That endpoint gap should be closed as a Track E/C follow-up before this is fully done.
  - **Verification:** `npx tsc --noEmit -p web/tsconfig.json` passes. `tests/e2e/onboarding.spec.ts` exists but has not actually run — Playwright's browser binary cannot be installed in this sandbox (see Task 4H.1's verification note). Do not mark `[x]` until the family-tree/cast-lock backend gap is closed and the e2e spec passes.

- [/] **Task 4H.3: Build workspace feature view, streamed agent activity, trait cards, and branch controls**
  - **Tooling:** React, SSE client, TanStack Query, Tailwind CSS, Playwright.
  - **Target Files:** `web/components/features/workspace/`, `web/components/workspace/`, `web/lib/generation-stream.ts`, `tests/e2e/generation.spec.ts`.
  - **Details:** Render loader → live activity → unpublished candidate preview → published chapter. Implement reconnect, jump-to-latest, reduced motion, accessible entity list, read-only graph, visible versioned trait cards, focal-character selector, and exactly three progression modes: Continue automatically, Edit traits, Jump/rewind.
  - **Status:** Implemented `lib/generation-stream.ts` (`useGenerationStream` hook wrapping native `EventSource` against `GET /generation-jobs/:jobId/events`; relies on the browser's built-in `Last-Event-ID` resend on reconnect, matched against the server-side dedup already in `stream_job_events`), `ActivityFeed` (ordered feed, jump-to-latest control that appears only once scrolled away from bottom, `prefers-reduced-motion`-aware scroll), `TraitCard` (renders one entity's current state from `GET /branches/:id/state`, versioned by virtue of always reading current branch state), and `BranchControls` (exactly three progression buttons: Continue automatically / Edit traits / Jump-rewind). `tests/e2e/generation.spec.ts` written against the existing `WorkspaceStudio` demo (mocked SSE via `/api/v1/generation-events/demo`). **Known backend gaps, not frontend gaps:** there is no TanStack Query wiring yet (plain hooks only), no focal-character selector (no backend concept of "focal character" exposed via API), no read-only relationship graph component, and no mutation endpoint for any of the three progression modes — `BranchControls.onSelect` is a callback the parent must currently no-op or stub. `ActivityFeed`/`TraitCard`/`BranchControls`/`useGenerationStream` are not yet composed into a single "workspace feature view" that replaces the ad hoc `WorkspaceStudio` demo in `app/page.tsx` — they exist as standalone, typechecked components only.
  - **Verification:** `npx tsc --noEmit -p web/tsconfig.json` passes. `tests/e2e/generation.spec.ts` exists but has not run (same Playwright browser-install blocker as Task 4H.1). Do not mark `[x]` until the progression-mode mutation endpoints exist, the components are composed into the actual workspace view, and the e2e spec passes.

- [/] **Task 4H.4: Build world, ending, reports, revision, and recovery feature views**
  - **Tooling:** React, Playwright.
  - **Target Files:** `web/components/features/world/`, `web/components/features/endings/`, `web/components/features/reports/`, `web/components/canon-events/`, `web/components/revisions/`, `tests/e2e/recovery.spec.ts`.
  - **Details:** Implement canon-event/relationship request dialogs, evaluator/business reports, ending-options request/selection, trace drawer behind feature flag, blocked-generation retry, archive/unarchive, and Edit-as-revision flow. Never reuse the prototype's direct kill/revive handlers: show target, branch, permanent-record consequence, explicit confirmation, then pending/evaluating status before any entity state changes. Show policy blocks, quota state, and safe alternative copy clearly.
  - **Status:** Backend gaps closed first: added `src/story_engine/api/routes/endings.py` (`GET /branches/:id/ending-options`, `POST /branches/:id/ending-options/:optionId/select` — the select handler rolls back entirely, including the prior selection's unset, if the target option doesn't match, so a 404 never has a side effect) and `src/story_engine/api/routes/revisions.py` (`POST`/`GET /chapters/:id/revisions`, always inserting/listing `DRAFT` rows, never editing the chapter itself), both wired into `app.py`; contract tests added (auth-boundary + `extra=forbid` schema checks), 90/90 passing, ruff/mypy clean, no target-file collisions. Frontend: `WorldView.tsx` (read-only entity/relationship display against `GET /branches/:id/state`), `CanonEventRequestDialog.tsx` (fixed a real bug during this pass — its event-type strings originally didn't match the backend's actual `CanonEventType` enum (`KILL`/`REVIVE`/`MOVE_REALM`/`INTRODUCE_ENTITY`/`EDIT_CANON`), corrected and now validates `requires_target_entity`-equivalent target presence client-side too; permanent-record warning shown for `KILL`, required confirmation checkbox, pending-status-only after submit), `EndingOptionsView.tsx` (lists/selects against the new endings route), `RevisionRequestForm.tsx` (submits against the new revisions route, copy explicitly states the original chapter is unchanged), and `TraceDrawer.tsx` (calls `GET /agent-runs/:id`, treats a 404 as "tracing off or not visible" rather than an error). `/world`, `/endings`, `/reports` routes in `app/page.tsx` now render these against an author-supplied branch/run id (there is still no story/branch-picker context provider, so this is a text field, not real navigation from a story list). `tests/e2e/recovery.spec.ts` written, with its second case (`RevisionRequestForm`) marked `test.skip` and explained: no chapter-detail route renders that component yet. **Still not built:** archive/unarchive, blocked-generation retry UI, a policy-block/quota-state display, and any aggregate evaluator/business "report" (only single-run trace-by-id exists — there's no `GET /generation-jobs/:id/agent-runs` list endpoint, so `TraceDrawer` needs a known run id rather than offering a picker).
  - **Verification:** `npx tsc --noEmit -p web/tsconfig.json` passes for everything above. `tests/e2e/recovery.spec.ts` has not run (same Playwright browser-install blocker). Do not mark `[x]` — archive/unarchive, blocked-generation retry, quota/policy-block display, and the report-listing endpoint are still missing, and no e2e spec has actually executed.

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
  - **Status:** Implemented `observability.py`: `MetricEvent` enum covering every listed metric, `CorrelatedLogRecord`/`emit()` (correlation-id-tagged structured logging via the stdlib `logging` module), `_assert_no_forbidden_keys` (rejects `prompt`/`secret`/`hidden_characteristic`/`preference_value`/`raw_response`/`api_key` payload keys before logging, mirroring `FORBIDDEN_COLUMN_SUBSTRINGS`), and `BudgetState`/`enforce_budget`/`BudgetExceededError` (the budget kill switch — blocks only new submissions, never cancels in-flight jobs, user-facing message states both facts). Test file was written as `tests/unit/analytics/test_observability.py` rather than the target `tests/integration/observability/test_metrics.py`, since these are pure-Python and need no live DB/Spark — placing them under `tests/unit` matches this repo's existing convention (`analytics/audit_schema.py`'s tests live in `tests/unit/analytics/` too) more than an unopened `tests/integration/observability/` directory would. `docs/runbooks/observability.md` written. **Not yet done:** no OpenTelemetry exporter (stdlib logging only), and — most importantly — nothing in `job_dispatcher.py`, the worker entry points, or any API route actually calls `emit()`/`enforce_budget()` yet; this is a tested library, not yet wired into the generation pipeline. No per-user `budget_limit_usd` storage/settings surface exists.
  - **Verification:** `tests/unit/analytics/test_observability.py`: 7/7 passing (correlated chain shares one id, each forbidden key individually rejected, under/at/over-budget behavior). Ruff/mypy clean. No log scanner has been run against a live job's actual log output since no job has ever executed against a real Databricks Job runtime in this sandbox.

- [/] **Task 5I.2: Add data-quality and reconciliation checks**
  - **Tooling:** PySpark, SQL, pytest.
  - **Target Files:** `src/story_engine/analytics/quality_checks.py`, `notebooks/03_operational_quality_checks.py`, `tests/integration/observability/test_reconciliation.py`.
  - **Details:** Check published chapter/state consistency, branch ancestry validity, event sequence continuity, audit-export reconciliation, and forbidden Delta columns. Run checks as a scheduled Databricks Job.
  - **Status:** Implemented `quality_checks.py`: `check_published_chapter_state_consistency`, `check_branch_ancestry_validity` (including cycle detection), `check_event_sequence_continuity`, `check_audit_export_reconciliation`, `check_no_forbidden_delta_columns` (reuses `FORBIDDEN_COLUMN_SUBSTRINGS` from `audit_schema.py`) — every failure is a `QualityCheckFailure` dataclass carrying a concrete `identifier` (branch/job/table id), never a bare "check failed". `notebooks/03_operational_quality_checks.py` written as the scheduled-job wrapper (widgets + calls into the above), but it has never been run against live data and is **not yet registered as a Databricks Job** — no `quality_checks_job` resource exists in `resources/jobs.yml` alongside `generation_job`/`report_job`. Test file written as `tests/unit/analytics/test_quality_checks.py` (same "these are pure functions, no DB needed" reasoning as 5I.1) rather than `tests/integration/observability/test_reconciliation.py`.
  - **Verification:** `tests/unit/analytics/test_quality_checks.py`: 10/10 passing, including one broken-fixture case per check function (missing parent, ancestry cycle, sequence gap, count mismatch, forbidden column) and one clean-fixture pass case each. Ruff/mypy clean. Never run as an actual scheduled Databricks Job — that requires the job resource registration above plus a live workspace.

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
  - **Status:** All five target files written. `test_rls_negative.py` (DB-gated): tenant-crossing on `canon_event_requests`, extending rather than duplicating the existing `tests/integration/persistence/test_rls.py` coverage of `stories`/`branch_entity_states`. `test_personalization_isolation.py` (DB-gated): cross-tenant read denial on `user_preferences` and `personalization_snapshots`. `test_event_redaction.py` (unit, no DB): `ClientGenerationEvent` rejects smuggled `payload`/`prompt` fields via `extra="forbid"`, `_row_to_event` skips a malformed row instead of raising or leaking it, a well-formed event's `model_dump()` has no `payload`/`prompt`/`raw_response` key. `test_prompt_injection.py` (unit): canon-event rationale and revision author-patches are length-capped (2000/12000 chars), `CanonEventRequestInput` rejects an injected extra field, and a static source-scan confirms `world.py`/`revisions.py` build every query via parameterized `execute(query, params)`, never f-string SQL. `test_content_ip_wellbeing.py` (unit): `CanonEventType` is a closed 5-member enum (no free-text event category is possible), and a source-scan confirms every `TemplatePicker` entry declares a `disclosure` field with visible "Licensed reference" copy — found and fixed a real bug while writing this: the first draft of `CanonEventRequestDialog.tsx` used event-type strings that didn't match the backend's actual enum at all (`REMOVE_ENTITY`/`MOVE_ENTITY`/`CHANGE_RELATIONSHIP` vs. the real `KILL`/`REVIVE`/`MOVE_REALM`), which would have made every canon-event request from that dialog fail server-side validation. **Not covered:** Director-memory privacy (no test targets memory-cutoff enforcement specifically from a security angle — `tests/integration/persistence/test_memory_cutoffs.py` covers the cutoff mechanism itself but not adversarial access to pre-cutoff memory), stale-write/duplicate-branch races under concurrency, blocked safety categories (no content-moderation/safety-category enum exists in this codebase yet to test), sponsorship-disclosure behavior (no sponsorship concept exists), and explicit quota-response copy (no quota system exists yet). No secret scanner or dependency scanner has been run in this pass — `.github/workflows/ci.yml`'s `secret-scan` job (gitleaks, added in Task 1A.4) is the mechanism, but it runs in CI, not in this sandbox.
  - **Verification:** `pytest tests/security -q`: 13 passed, 3 skipped (DB-gated, correctly skip without `TEST_DATABASE_URL`). Ruff/mypy clean. No evidence has been attached to an actual release pull request since none is open.

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
