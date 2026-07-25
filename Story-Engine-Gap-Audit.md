# Story Engine — Cross-Document Gap Audit

**Scope reviewed:** `design.md`, `task.md`, `requirements.md` (hackathon folder — treated by `task.md` as source of truth), plus three uploaded reference documents: `story-engine-requirements.md` (original, richer requirements draft), `story-engine-backend-design-final.md` (earlier backend design), and the clickable prototype (`StoryEngineProto.jsx` / `.html`).

**Method:** read all six documents in full, cross-referenced every numeric limit, every screen/flow description, every data-model decision, and every "deferred/decided" statement against the other five documents, and diffed the prototype's actual behavior against `design.md`'s UI rules. Findings are grouped by severity. Each finding names the exact source and gives a concrete fix.

---

## 1. Critical contradictions (will cause a wrong implementation if not resolved before Phase 4)

### 1.1 The prototype directly violates `design.md`'s hidden-characteristic rule — and the reason is a real, undocumented design reversal

`design.md` §"Hidden characteristic rule" is unambiguous: *"Do not show a blur, 'secret exists' badge, or hint in roster, graph, reader, API payload, trace summary, or reports until a story reveal has been committed."*

The uploaded prototype (`StoryEngineProto.jsx`, lines 1227–1230) does exactly the forbidden thing on the Cast screen:
```
<div className="se-hidden-row">
  <div className="se-hidden-label"><Lock size={10}/> Hidden characteristic</div>
  <p className="se-hidden-line">{c.hidden}</p>   {/* rendered, then CSS-blurred */}
  <p className="se-hidden-note">Concealed from view — may surface as a twist...</p>
</div>
```
This is not a stray prototyping mistake — it implements a feature that `story-engine-backend-design-final.md` (§6.1, `stories.genres` column) **explicitly specifies**: *"genres... drives feature gating, e.g. Mystery/Detective genre enables hidden characteristics being surfaced in the UI as a locked/blurred hint."*

So there are two prior, real design artifacts (backend design + prototype) that built a "blurred hidden-trait hint" as a genre-gated feature, and `design.md` silently reverses that decision with a blanket ban — without ever saying so. `task.md`'s §0.4 reconciliation table has a row for "Hidden traits versus inspectable traits" but it only addresses *mutable* trait inspectability, not this specific blur/hint feature or the genre-gating mechanism tied to it.

**Risk:** an implementer who opens the prototype or the backend design (both handed over as source material) as a reference for the Cast screen will build the blurred-hint UI, which is a direct spec violation and a real privacy/spoiler bug.

**Fix:** add an explicit line item to `task.md` §0.4 and to `design.md`'s hidden-characteristic section: *"Supersedes: the genre-gated blurred-hint feature in `story-engine-backend-design-final.md` §6.1 and the prototype's Cast screen hidden-row UI are explicitly removed, not just superseded implicitly."* Add a DOM-scan negative test (task 4H.2 already tests "no hidden-characteristic hint" — extend its fixture list to include the removed blur pattern by name so a reviewer can trace it back to this decision).

### 1.2 Prototype enforces a hard 20-character minimum; `design.md`, `requirements.md`, and the richer `story-engine-requirements.md` all disagree with each other on this exact point

- `story-engine-requirements.md` FR-1.2: *"No minimum length enforced... very short input... triggers the clarification flow."*
- `design.md` config table: *"Short-input clarification threshold: 12 tokens... never silently rejects a short creative seed."* (no hard minimum, measured in tokens)
- hackathon `requirements.md` (the file `task.md` calls the source of truth) §"Initial Configurable Limits": *"Seed prompt length | 20–2,000 characters"* — this reads as a hard 20-character **minimum**, contradicting the other two documents and its own MVP principle.
- The prototype (`StoryEngineProto.jsx` line 898, 970) hard-codes this literally: `canAdvance = prompt.trim().length >= 20` blocks the Next button, with visible copy *"minimum 20 characters"* — i.e., it silently blocks progress instead of opening the clarification loop the requirements mandate.

**Risk:** three source documents disagree on units (characters vs. tokens) and on mechanism (hard block vs. clarification loop). If a builder works from `requirements.md` or the prototype literally, they will implement a silent hard-reject, which directly violates GR-3.1 ("no AI decision... silently committed") and FR-1.2.

**Fix:** correct the hackathon `requirements.md` limits table row to read *"Seed prompt length: up to 2,000 characters; inputs below the clarification threshold (~12 tokens) open a confirmation loop, never a hard block"* — i.e. make it match `design.md`, and add a note to `task.md` Task 4H.2 to explicitly discard the prototype's `>=20` gate rather than port it.

### 1.3 Prototype's World Sandbox performs direct kill/revive/realm-change with no evaluator step or confirmation dialog; `design.md` requires both

`design.md` retired direct mutation endpoints on purpose: *"The earlier direct status/realm/entity mutation endpoints are intentionally replaced by `canon-event-requests` in MVP... to honor the required evaluator review."* It also requires: *"Destructive or high-impact canon-event requests require an explanatory confirmation dialog with target, branch, consequence, and 'This creates a permanent canon-event record' copy."*

The prototype (lines 1656–1658) wires Kill/Revive to an immediate, unconfirmed local state change:
```
<button onClick={() => setStatus(c.id, "DECEASED")}><Skull/> Kill</button>
<button onClick={() => setStatus(c.id, "ACTIVE")}><Heart/> Revive</button>
```
with no dialog, no evaluator round-trip, no "pending" state. This matches the **older** `story-engine-backend-design-final.md` §3.1 model (*"direct, user-initiated canon writes... straight to the world agent"*), which `design.md` has since overridden.

**Risk:** same as 1.1/1.2 — the prototype is handed over as a UI reference, and its actual click-through behavior for the single most safety-sensitive screen (killing a character) is the exact pattern `design.md` calls out as no longer acceptable.

**Fix:** `task.md` Task 4H.4 already targets `web/components/canon-events/`, which is correct — but add an explicit acceptance note: *"Do not reuse the prototype's direct kill/revive handlers; canon-event dialogs must submit a request and show a pending/evaluating state before any status change renders."*

### 1.4 Prototype's progression flow has no "Continue automatically / Edit traits / Jump-Rewind" composer at all

`design.md`'s entire progression model — the three-mode composer that `task.md`'s own decision table calls a locked, hard requirement (*"Implement exactly: Continue automatically, Edit traits, Jump/rewind... not the progression control"*) — does not exist in the prototype. The prototype's reader screen (lines 1433–1454) only offers two fixed storyteller choices plus a custom-text field, then a single "Progress to Chapter N" button. There is no focal-character selector, no trait-edit entry point, no rewind/jump entry point anywhere in the file.

**Risk:** low on its own (task.md's Track H tasks correctly target the new composer), but worth flagging explicitly because it means the prototype cannot be used as a structural reference for the single most-tested user flow in the whole app (Task 4H.3's E2E acceptance criteria). Currently nothing in `task.md` says this outright — an implementer skimming the prototype for "what does the reader screen look like" gets a materially incomplete picture.

**Fix:** add a short note to `task.md` Track H preamble: *"The prototype implements a pre-redesign 2-choice progression model. It is a visual/tone reference only for typography, color, and card layout — the progression composer, cast hidden-trait row, and World Sandbox actions must be built from `design.md` §2/§4, not from the prototype's interaction logic."* This one sentence would have prevented findings 1.1, 1.2, 1.3, and 1.4 from being ambiguous.

---

## 2. Requirements-traceability gaps (things asked for in the requirements docs that never made it into `design.md`/`task.md`, with no explicit deferral)

### 2.1 A second, richer requirements document exists and is never reconciled

The hackathon `requirements.md` is a condensed rewrite. The uploaded `story-engine-requirements.md` ("Interactive Story Engine — Requirements Document," owner Astik) is a longer, earlier document with real content that doesn't appear in the condensed version or in `design.md`/`task.md`, and nothing in either file says "this document is superseded, here is what changed and why." Specifically missing or unaddressed:

- **§8 Monetization & business model** (genre-weighting disclosure, sponsored/branded chapters, "shop the scene," sponsored template labeling, A/B-testing disclosure rules) is almost entirely absent from `design.md`. The only trace is a single phrase in `task.md` Task 2D.4 ("disclosed genre weighting/sponsorship fields") inside a test-file description — there is no screen spec, no data model field, no UI component (a "Presented by [Brand]" badge, a "shop the scene" link) anywhere in `design.md`'s Template Library or Concept Selection screen specs. If monetization is intentionally out of scope for this build, `task.md` needs to say so explicitly instead of leaving one orphaned test-file reference; if it's in scope, `design.md` §4 needs a screen/component spec for it.
- **GR-5.2** (harmful trait-spiral nudging: *"if a user repeatedly edits a character toward self-destructive, abusive, or degrading traits... offer a gentle nudge rather than mechanically complying"*) has no corresponding rule anywhere in `design.md`'s Content Safety section or `task.md`'s policy-gate tasks (2D.4, 3E.4). GR-5.1 (real-distress detection) is covered; GR-5.2 is not.
- **GR-4.1** (dream-mode personal/sensitive content must not be used for model training/fine-tuning beyond the session without explicit consent) has no corresponding statement in `design.md`'s Security/Data Boundaries section, which otherwise is very thorough about isolation and redaction. Training-data usage/consent is a distinct claim that's simply missing.
- **FR-2.2** (animated portrait/avatar, short looping animation) is dropped without being named in `design.md`'s "Deferred MVP Boundaries" list (which only names image/comic generation, collaboration, vector retrieval, and branch pruning). "Animated portraits" should be added to that list explicitly so it's traceable as a conscious deferral rather than a silent drop.
- **§10 Success metrics** (comic-export rate, branch-usage rate, trait-edit acceptance rate) has no counterpart task. `task.md` Task 5I.1 covers technical/operational metrics (latency, retries, RLS denials) but nothing about product/business metrics. If these matter for a hackathon demo or investor narrative, there's currently no instrumentation task that would produce them.
- **§9 Open question 5** ("session/quota limits... need actual numbers before build") is still open. `design.md` says *"Enforce configurable per-owner concurrent-job and rate limits"* but never states actual default numbers, and no task in `task.md` explicitly assigns "decide and document the default quota numbers" as a deliverable. This should be a named task before Phase 4/5, not an implicit assumption.

**Recommendation:** add a short "Requirements Reconciliation" appendix to `design.md` (or a new ADR under `docs/adr/`) that explicitly lists every FR/GR/MON item from `story-engine-requirements.md`, states Implemented / Deferred / Out-of-scope for each, and gives a one-line reason. This closes the traceability hole in one document instead of leaving it implicit across three files.

### 2.2 Family tree relationship auto-suggestion (FR-3.2) is narrowed without saying so

FR-3.2 requires that introducing a new character mid-story "gets folded into the existing family tree with system-suggested relationships to existing characters." `design.md`'s `CanonEventRequest` for `INTRODUCE_ENTITY` only carries a `proposedPayload` and `rationale` — there's no mention of the system proposing relationship suggestions as part of that flow. Minor, but worth a one-line addition to the Canon Event dialog spec (§4, World Control Sandbox) so the relationship-suggestion behavior isn't lost in translation.

---

## 3. Internal inconsistencies within `design.md` / `task.md` themselves

### 3.1 Several "configurable" limits referenced in prose are missing from the Configurable Product Limits table

`design.md` §1's limits table is presented as the canonical list of guardrails that "must be configuration, not hard-coded," but the following values are referenced elsewhere in the same document as configurable and never appear in that table:
- Number of storyteller-generated branching choices per chapter (backend design says "2 branching choices"; `design.md` shows "Choice A / Choice B" in the layout blueprint but never states this is configurable or gives a default in the limits table).
- Minimum chapter count before manual "show ending options" is allowed (§4 Ending Options: "the configured minimum chapter count" — no default given anywhere).
- Ending-eligibility pacing heuristic thresholds (§4: "configurable pacing heuristics" — undefined).
- Per-owner concurrent-job / rate-limit numbers (§6 Edge Cases: "configurable per-owner concurrent-job and rate limits" — undefined, same gap as §2.1's open question 5).

**Fix:** extend the §1 limits table with these four rows (even with placeholder defaults marked "TBD — confirm before Phase 5 release checklist"), so `task.md`'s Task 5J.3 release checklist has something concrete to verify against.

### 3.2 Genre-based feature gating is now orphaned data

Because of finding 1.1, the `stories.genres` "drives feature gating" note from the backend design is no longer valid, but `design.md`'s data model doesn't re-state what `genres` is used for now. Currently `design.md` only says genres are used to "suggest concepts, default seed controls, and storyteller style guidance" (personalization table) — that's fine, but the backend design's now-obsolete feature-gating note should be explicitly retired in the schema section (§5) rather than left unaddressed, since `stories.genres` is a carried-over column and a future reader could reintroduce the retired behavior.

### 3.3 First-time user provisioning isn't specified

`design.md` and `task.md` both assume a `users` table scoped by `user_id` under Databricks Apps OAuth, but neither document states how a user row gets created on first login (just-in-time provisioning vs. a separate signup step). Task 2C.1 creates the schema; no task in Track G (API) or Track D (domain) owns "create-user-on-first-authenticated-request" logic. Worth a one-line addition to Task 4G.2.

### 3.4 No task owns actual prompt content / system-prompt authoring and adversarial testing depth

Task 3E.2 says agents must implement "distinct typed interfaces and system policies," and Task 2D.3 covers prompt-injection defenses structurally, but no task explicitly owns writing and iterating the real system prompts (Director/World/Storyteller/Evaluator/Business) for narrative quality, nor a red-team pass beyond the adversarial-fixture unit tests in 2D.3. For a hackathon build this is often the single biggest source of "the demo doesn't feel good" risk, and it currently has no owner or acceptance criteria distinct from the mechanical typed-schema tests.

### 3.5 Template-library legal/licensing sign-off has no task owner

`design.md` and `task.md` both require templates be "originally authored or verified licensed" (GR-1.3, Task 2D.4's `template_policy.py`), but the actual authoring/licensing review of template *content* — who writes the templates, who signs off that a license is "confirmed" — is not a task anywhere in Phase 1–5. The code enforces the policy field; nothing produces the templates or the licensing evidence that field is supposed to gate.

### 3.6 No cost/spend guardrail despite cost being a stated design driver

`design.md`'s architectural principles repeatedly cite cost as a reason for bounding fan-out (*"Controls fan-out cost," "Bounded generation latency and cost"*), but there's no metric, budget alert, or kill-switch anywhere in `design.md` §Observability or `task.md` Track I for actual LLM spend per job/story/user. Given the fan-out (up to 4 characters × 2 discussion rounds × Director/World/Storyteller/Evaluator/Business calls per chapter), this is a real operational risk with no monitoring task assigned.

### 3.7 No automated accessibility/contrast verification task

`design.md` §6 requires WCAG AA contrast validated "for both default and configurable themes," and Task 4H.1's Playwright test only checks 200%-zoom layout and keyboard nav — there's no automated contrast-scan (e.g., axe-core) task anywhere in Track H or Track J. This is a stated hard requirement with no verification step in the build plan.

---

## 4. Lower-priority observations

- `design.md`'s Reference Architecture correctly modernizes the stack from the requirements doc's "PostgreSQL + Redis-backed jobs" (hackathon `requirements.md` §MVP Scope) to "Lakebase Postgres + Databricks Jobs" — this is a deliberate, well-documented platform decision and is *not* a gap, just noting it for completeness since it's a real divergence from `requirements.md`'s stated stack that isn't called out as a correction inside `requirements.md` itself (the requirements doc still says "Redis-backed asynchronous jobs," which is stale).
- The parallel-director-agent cap default differs across documents: backend design suggests 6 as an example ("cap concurrent... e.g. 6"), while `design.md`/`requirements.md` agree on 4. This is resolved (design.md wins), just confirm no stray "6" survives into implementation defaults.
- `task.md`'s track-isolation model ("do not begin a task that edits another active track's target path") is a good discipline but was not verified in this audit for actual path collisions across all ~30 tasks; recommend a quick static check (a script that greps every "Target Files" line and flags duplicates across concurrently-runnable tracks) before Phase 3/4 kick off, since Track E/F and G/H both touch `services/` and `components/` boundaries that are easy to blur in practice.
- No task explicitly validates that `agent_trace_enabled` redaction is tested against every agent type (director, world, storyteller, evaluator, business) individually — Task 2D.2 tests redaction generally; confirm its fixture matrix actually enumerates all five agent output shapes, not just a generic event.

---

## 5. Summary table

| # | Finding | Severity | Where | Fix owner |
|---|---|---|---|---|
| 1.1 | Prototype/backend-design blur hidden trait on genre; design.md bans it, reversal undocumented | Critical | Cast screen | Add explicit supersession note + DOM-scan test |
| 1.2 | Hard 20-char minimum in prototype & stale requirements.md row vs. design.md's clarification-loop model | Critical | Seed screen | Fix requirements.md table; discard prototype gate |
| 1.3 | Prototype kills/revives with no evaluator step or confirm dialog; design.md requires both | Critical | World Sandbox | Explicit non-reuse note in Task 4H.4 |
| 1.4 | Prototype has no 3-mode progression composer at all | High | Narrative Workspace | Add "prototype is visual reference only" note to Track H |
| 2.1 | Richer requirements.md (monetization, GR-5.2, GR-4.1, animated portraits, success metrics, quota numbers) never reconciled | High | Cross-doc | Add Requirements Reconciliation appendix/ADR |
| 2.2 | Auto-suggested relationships on character introduction dropped silently | Low | Canon Event dialog spec | One-line spec addition |
| 3.1 | Several configurable limits referenced but missing from the limits table | Medium | design.md §1 | Add 4 rows with defaults/TBD |
| 3.2 | Orphaned `genres` "feature gating" schema note | Low | design.md §5 | Retire the note explicitly |
| 3.3 | No first-login user-provisioning task | Medium | Task 4G.2 | Add JIT user creation subtask |
| 3.4 | No task owns real prompt authoring/red-teaming | Medium | Task 3E.2 | Add explicit prompt-quality task |
| 3.5 | No task owns template licensing sign-off | Medium | Phase 1/Track B | Add content/legal task |
| 3.6 | No LLM cost/budget monitoring task | Medium | Task 5I.1 | Add spend metric + alert |
| 3.7 | No automated contrast/accessibility scan task | Medium | Task 4H.1/5J.1 | Add axe-core (or similar) task |

---

## 6. Recommended next action

Before Phase 4 (UI build) starts, resolve the four Critical items in §1 — they are the ones most likely to produce a working-but-wrong build, since the prototype and the older backend design are both handed to implementers as reference material and actively contradict the current `design.md`. A single short addendum to `task.md` §0.4 ("Prototype Deviation Log") listing items 1.1–1.4 by name would close most of the practical risk in under an hour of writing.
