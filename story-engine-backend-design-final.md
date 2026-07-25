# Story Engine — Backend Design (Final)

## 1. Design principles

- **One agent, one job.** Narrative generation, character behavior, world-state truth, consistency checking, and "everything else" (export, formatting, art prompts, moderation) are handled by separate agents so each one keeps a small, focused context and can be tuned/swapped independently.
- **World agent is the single source of truth.** No other agent is allowed to silently mutate canon (who's alive, where things are, what's happened, what's been revealed). Everything funnels through it.
- **Character agents are personas, not writers.** A director agent's job is to decide what *its* character wants and does next — not to write final prose. The storyteller agent turns those decisions into scenes.
- **Chapter generation is a discussion, not a single pass.** Each chapter is produced by a bounded back-and-forth between the director agents, the world agent, and the storyteller agent — not one-shot generation (see §3).
- **The LLM knows more than the player does.** Hidden characteristics live in agent context from the moment a character is created, but are redacted from every user-facing surface until the story itself reveals them (see §5.5).
- **Memory is simple today, swappable tomorrow.** v1 uses flat structured rows in Postgres (recency + importance, no embeddings). The schema is shaped so a vector/RAG layer can be added later without a rewrite (see §4.6).

---

## 2. Agents

| Agent | Cardinality | Responsibility | Does NOT do |
|---|---|---|---|
| **Orchestrator** | 1 per request | Sequences the pipeline below, runs the director ⇄ world-agent discussion loop, retries/timeouts, assembles final payload | Any generation itself |
| **World agent** | 1 per story | Owns canon: realms, entity states, timeline, world rules, relationships, hidden-characteristic reveal state. Validates every proposed change before it's committed | Write prose, decide character intent |
| **Character director agent** | 1 per *active* character (spun up on demand, not persistent processes) | Given world context + its character's memory (including its own screenplay history and its own hidden characteristic) decides that character's goal/action/line for the current beat, in-voice | Decide other characters' actions, narrate, touch canon directly |
| **Storyteller agent** (formerly "story creator agent") | 1 per story generation step | Takes world state + all validated director outputs for the beat and composes them into structured **scenes** (slugline, action, per-character dialogue) plus choice branches and, when relevant, comic panel breakdowns. May *propose* surfacing a hidden characteristic as a story beat — subject to world-agent approval | Decide character motivations from scratch (it adapts director output, doesn't invent it), do art/export work, reveal hidden characteristics on its own authority |
| **Evaluator agent** | 1 per chapter (runs after publish, or on demand) | Re-reads the chapter against each active character's locked core profile and against locked canon facts. Flags any character whose voice/behavior diverged from how they were defined at cast-lock, and any world-fact contradiction | Fix the divergence itself — it only reports |
| **Business agent** | 1 per chapter (runs after publish, or on demand) | Scores the chapter for narrative interest (hook strength, pacing, stakes clarity, character likability) and writes a short verdict/notes | Touch canon, touch character memory |
| **Utility agent** | 1 per task | Non-creative work: art/image prompt generation for comic panels, PDF/EPUB export formatting, content moderation pass, summarization for memory compaction, seed-concept drafting at onboarding | Anything that touches canon or in-character decisions |

### 2.1 Why split "storyteller" from "character director"

If one agent both decides what Kaelen wants *and* writes the final scene, two problems show up fast: the agent has to hold every character's voice + the prose style + pacing all in one context (memory bloat, drift), and you can't parallelize — you can't ask 4 character agents "what do you do next" concurrently if writing is entangled with deciding. Splitting them lets director agents run in parallel per beat, and lets the storyteller agent be the only thing that needs "how this story sounds" as a concern.

### 2.2 Why the world agent is a gatekeeper, not just a data store

Director agents will happily propose "Kaelen kills the Guild leader" even if the Guild leader is in a different realm this beat. The world agent's job is to receive proposed actions, check them against current entity state/location/relationships, and either approve, adjust ("Kaelen can't reach him this beat — redirect"), or reject with a reason. A rejection isn't the end of the exchange — it's fed back to the director agent as part of the same chapter's discussion (see §3).

### 2.3 Why evaluator and business agents are separate from the world agent

The world agent enforces *hard* consistency (a dead character can't act). The evaluator agent checks *soft* consistency — does Mira Voss's dialogue this chapter still sound like the "clipped, procedural, quietly menacing" character locked at cast-setup, or has she drifted? That's a judgment call, not a rule, so it's a read-only report rather than something that blocks generation. The business agent is judgment of a completely different kind (is this actually a good chapter?) and has no business seeing canon-write authority either — both are downstream, advisory agents that run after the chapter exists.

---

## 3. Orchestration: chapter generation pipeline

Chapter generation is modeled as a **discussion with a bounded number of rounds**, not a single linear pass — the director agents and the world agent go back and forth until every active character's action is either approved or the retry budget is exhausted.

```
1. Orchestrator receives "generate next chapter" (arc_id, chapter context, any free-text
   user input from the previous chapter's branching decision)
2. → World agent: load current canon snapshot (entities, relationships, realm, open
     objectives, which hidden characteristics are unrevealed)
3. → World agent: determine which characters are "active" this beat (present in current
     realm, alive, not exiled)
4. → Persist the incoming user input as a `chapter_user_inputs` row (what they typed/chose)

   ── DISCUSSION ROUND (repeats up to `max_discussion_rounds`, default 2) ──
5. → Character director agents (parallel, one call per active character):
     input:  world snapshot + this character's core profile + recent episodic memory
             + this character's own recent screenplay lines (§4.2) + this character's
             own hidden characteristic (never another character's) + (round > 1 only)
             the world agent's rejection reason from the previous round
     output: { intent, proposed_action, dialogue_line, emotional_state }
6. → World agent: validate each proposed action against canon
     - approve as-is
     - adjust (location/relationship constraints) — treated as approved
     - reject (with reason) → loop back to step 5 for that character only, next round
   ── END DISCUSSION ROUND — any character still rejected after max rounds is handed
      to the storyteller agent as "constrained: write around this" rather than looping
      forever ──

7. → Storyteller agent: given world snapshot + validated character outputs → produce
     - one or more **scenes**: slugline, action text, ordered per-character dialogue
       lines (this *is* each character's screenplay for the chapter)
     - 2 branching choices (or resolves an existing choice)
     - if comic mode: panel breakdown (visual description, camera, speech, caption)
     - optionally: a *proposal* to reveal a specific character's hidden characteristic
       as part of this chapter's events (see §5.5) — a proposal, not a write
8. → World agent: commit resulting state changes (new relationships, status changes,
     location changes, new canon facts, hidden-characteristic reveal if the storyteller's
     proposal is approved) — this is the only write path to canon
9. → Orchestrator: persist chapter (scenes + dialogue_lines), append each character's
     new lines to their own `character_screenplay_lines`, persist memory deltas
10. → Utility agent (parallel, non-blocking where possible):
     - generate image prompts for comic panels
     - moderation pass on generated scenes
11. → Evaluator agent + Business agent (parallel, run once the chapter is committed):
     - evaluator: produces an `evaluator_reports` row + per-character and per-world-fact
       check rows
     - business: produces a `business_reports` row + per-metric breakdown rows
12. → Orchestrator: return full payload (scenes, dialogue, choices, evaluator summary,
     business summary) to client
```

Key rules:
- **Steps 5–6 are the only part that loops**, and only per-character, only up to `max_discussion_rounds`. This keeps the discussion bounded and cheap.
- **Step 8 is the only serialized write** to canon (including hidden-characteristic reveals). Steps 5, 10, and 11 fan out in parallel; this avoids race conditions on canon without serializing the expensive generation calls.
- **Steps 11 run after commit**, not before — the evaluator and business agents review the chapter as published, not a draft, so their reports are stable and re-runnable on demand (Screen 8's "Re-run both agents").

### 3.1 World Sandbox / Screen 6 actions (kill, revive, change realm, restart arc)

These are **not** run through the director/storyteller pipeline — they're direct, user-initiated canon writes. They go straight to the world agent (steps 2/8 only), because they're explicit user commands, not narrative decisions. A "restart arc" (Screen 6B) is the exception that also calls the utility agent to draft the 3 arc-premise options, then the world agent snapshots which entities/relationships carry over.

### 3.2 Introducing a new character mid-story

Also a direct world-agent write, not part of the discussion loop: the user (or the storyteller agent, subject to world-agent approval) creates a new `entities` row with `introduced_in_chapter_id` set to the current chapter. Unlike predefined cast, an introduced character has no cast-lock restriction — the user can keep editing its role/voice/traits going forward, since it was never part of the "locked at start" set (see §5.4).

---

## 4. Memory design

### 4.1 Character memory — three buckets

Each character has three memory buckets:

- **Core profile** (slow-changing): personality traits, speech pattern notes, standing goals, fears, and the character's **hidden characteristic** — set at cast setup (or, for introduced characters, at introduction), edited rarely, and locked once the arc's cast is locked. Loaded in full every time the director agent runs.
- **Episodic log** (append-only): one row per notable event the character experienced/caused, tagged with an `importance` score (1–5, set heuristically by the utility agent during memory compaction).
- **Screenplay memory** (append-only): every dialogue line the character has actually spoken on the page, in order, tied to the scene/chapter it was said in. This is what lets the director agent stay in-voice ("what did I already say about this?") without re-reading full chapter prose. Stored in its own table (§6.4) rather than folded into the episodic log, because it's retrieved differently — always "my own last N lines," never another character's.

### 4.2 Retrieval strategy (v1)

No embeddings, no vector search. On each director agent call:
1. Load full core profile (including hidden characteristic — director agents always see their own character's).
2. Load last N (default 15) episodic rows for that character, ordered by `chapter_index desc`.
3. Load any episodic rows with `importance >= 4` regardless of age (so a character never "forgets" that their mentor died, even 20 chapters later).
4. Load last M (default 20) of that character's own `character_screenplay_lines` rows, so the director agent knows what it has already said.

This is a context-window budget problem, not a retrieval-quality problem, at this stage — simple recency + importance floor is enough.

### 4.3 World / story memory

The world agent works off:
- `entities` (current state — always current, not historical)
- `canon_facts` (append-only lore/history — once `locked = true`, it can only be superseded by an explicit new fact, never edited)
- `relationships` (current + historical, scoped per arc since relationships can change across arc restarts)

### 4.4 Memory compaction

After each chapter commits, the utility agent runs a cheap summarization pass: it reads the new episodic events and screenplay lines and (a) assigns importance scores to episodic rows, (b) optionally collapses low-importance old episodic rows (e.g. >30 chapters old, importance ≤2) into a single "summary" row per character, to keep the episodic table from growing unbounded. Screenplay lines are never collapsed or deleted (they're small, and losing a character's exact past lines defeats the point) — only the *retrieval window* (§4.2 step 4) limits what's loaded per call.

### 4.5 What a director agent can never see

A director agent is given its own character's core profile, episodic memory, and screenplay memory — never another character's hidden characteristic, and never another character's screenplay memory unless it's phrased as dialogue that character heard (i.e. it comes in through the world snapshot's scene description, not through direct memory access). This is a context-assembly rule enforced by the orchestrator when it builds each director agent's input, not a database permission.

### 4.6 Upgrade path (explicitly deferred, not built now)

The schema stores `content`/`line` fields as plain text and adds an `embedding` column (nullable) on `character_memory`, `character_screenplay_lines`, and `canon_facts` from day one — unused in v1, but means switching retrieval from "last N + importance floor" to "vector similarity + importance floor" later is a query change, not a migration.

---

## 5. Consistency enforcement

1. **Single writer per fact type.** Entity state, relationships, canon facts, and hidden-characteristic reveal status are only ever written by the world agent (pipeline step 8). Director/storyteller agents propose; they never write.
2. **Validation before commit.** Every proposed action is checked against: entity `status` (a DECEASED entity can't act), entity `location` (can't interact with something not in the same realm unless explicitly traveling), and existing `canon_facts` marked `locked`.
3. **Canon locking.** Once a chapter is published (`status = PUBLISHED`), the canon facts and entity-state deltas it produced are locked. A branch/alt-chapter can propose a *divergent* state, but it's scoped to its own branch (`branch_parent_id`) until/unless it's the one that gets published.
4. **Predefined cast is locked at arc start, not per-chapter.** Every entity created during cast setup (Screen 3) has `introduced_in_chapter_id = NULL`. While `arcs.cast_locked = false`, the user can freely edit name/role/voice/traits/visual/hidden_characteristic for these entities. The moment cast is locked (`POST /arcs/:id/cast/lock`, "Lock cast & launch Chapter 1"), those fields become read-only for the life of the arc — only `status` and `current_realm_id` can change after that (matches Screen 6: "founding cast ... only status and location"). Characters introduced later (`introduced_in_chapter_id` set) are never subject to this lock, since they didn't exist at cast-lock time.
5. **Hidden characteristics are agent-visible, user-invisible, until revealed.** Every entity may have a `hidden_characteristic`. It is included in full for every agent context (director, world, storyteller, evaluator) from the moment the entity is created — the LLM side always knows. It is stripped from every user-facing API response (`GET /entities/:id`, roster endpoints, etc.) unless `hidden_characteristic_revealed = true`. The only way that flag flips is a world-agent commit at pipeline step 8, triggered either by a storyteller-agent proposal in step 7 or a direct authored reveal (e.g. an author explicitly forcing a reveal from Screen 6/7). This makes the reveal itself a canon event, so it's timestamped, chapter-attributed, and can't be silently un-revealed.
6. **Arc restarts version, not delete.** Restarting into a new arc snapshots which entities/relationships are retained (`arc_carryover`) rather than mutating history — old arcs stay queryable.
7. **Evaluator findings never auto-correct canon.** If the evaluator agent flags a character as diverged, that's a report row, not a rollback — a human (or a future authored fix-up chapter) decides what to do with it. This keeps the evaluator's read-only status enforced by design, not just convention.

---

## 6. Database schema

Postgres, all IDs UUID, all tables have `created_at`/`updated_at` unless noted.

### 6.1 Core story structure

**`users`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| email | text | |
| display_name | text | |

**`stories`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → users | |
| title | text | |
| seed_type | enum | CUSTOM / DREAM_FRAGMENT / PARTIAL_STORY / PRESET |
| seed_prompt | text | raw user input from Screen 1 |
| genres | text[] | drives feature gating, e.g. Mystery/Detective genre enables hidden characteristics being surfaced in the UI as a locked/blurred hint |
| tone | text | |
| art_style | text | |
| status | enum | ACTIVE / ARCHIVED |

**`concepts`** — the 3 generated options on Screen 2, kept for history
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| story_id | uuid FK → stories | |
| title, tagline, summary, core_conflict | text | |
| seed_entities | jsonb | entity stubs proposed at concept stage |
| selected | boolean | which one the user picked |

**`arcs`** — a story can be soft-restarted into a new arc (Screen 6B) while keeping some roster
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| story_id | uuid FK → stories | |
| concept_id | uuid FK → concepts, nullable | null for arcs created via restart, not initial concept selection |
| premise | text | editable arc pitch |
| objectives | text[] | |
| retained_realm_id | uuid FK → realms, nullable | |
| status | enum | ACTIVE / ARCHIVED |
| arc_index | int | ordering within a story |
| cast_locked | boolean | false until "Lock cast & launch Chapter 1"; gates predefined-entity edits (§5.4) |
| cast_locked_at | timestamptz, nullable | |

**`arc_carryover`** — what was explicitly kept when this arc was created via restart
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| arc_id | uuid FK → arcs | the *new* arc |
| source_arc_id | uuid FK → arcs, nullable | the arc restarted from |
| entity_id | uuid FK → entities | |

### 6.2 World state

**`realms`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| story_id | uuid FK → stories | |
| name | text | |
| description | text | |
| parent_realm_id | uuid FK → realms, nullable | for nested locations |

**`entities`** — characters, objects, locations-as-entities, factions/AI
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| story_id | uuid FK → stories | |
| type | enum | HUMANOID / OBJECT_ARTIFACT / LOCATION_BUILDING / SENTIENT_AI / FACTION |
| name | text | |
| role | text | free-text role/title shown in roster |
| voice | text | speech pattern / dialogue style, set at cast setup — HUMANOID only |
| traits | text | core traits, set at cast setup — HUMANOID only |
| status | enum | ACTIVE / DECEASED / EXILED |
| current_realm_id | uuid FK → realms | current location — always current, not historical |
| visual_description | text | used for comic panel / image prompts |
| is_user_avatar | boolean | true for the "insert yourself" character |
| current_arc_id | uuid FK → arcs | which arc this entity is actively part of |
| introduced_in_chapter_id | uuid FK → chapters, nullable | **NULL = predefined at cast setup** (subject to cast-lock, §5.4); non-null = introduced mid-story (never locked) |
| hidden_characteristic | text, nullable | agent-visible always; user-visible only once revealed (§5.5) — HUMANOID only |
| hidden_characteristic_revealed | boolean | default false |
| hidden_characteristic_revealed_chapter_id | uuid FK → chapters, nullable | which chapter's events revealed it |

**`relationships`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| arc_id | uuid FK → arcs | relationships are scoped per arc |
| from_entity_id | uuid FK → entities | |
| to_entity_id | uuid FK → entities | |
| label | text | e.g. WIELDER_OF, ENEMY_OF, LOCATED_IN |
| established_in_chapter_id | uuid FK → chapters, nullable | |
| superseded_by_id | uuid FK → relationships, nullable | for relationship changes over time |

**`canon_facts`** — world agent's lore/history ledger
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| story_id | uuid FK → stories | |
| fact_type | enum | LORE / RULE / HISTORY_EVENT / HIDDEN_REVEAL |
| content | text | |
| established_in_chapter_id | uuid FK → chapters, nullable | |
| locked | boolean | true once the source chapter is published |
| embedding | vector, nullable | unused in v1, reserved for future RAG |

### 6.3 Narrative content

**`chapters`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| arc_id | uuid FK → arcs | |
| branch_parent_id | uuid FK → chapters, nullable | non-null for alt/branch chapters |
| chapter_index | int | ordering |
| title | text | |
| status | enum | DRAFT / PUBLISHED / BRANCH_OPTION |
| exported | boolean | |

Chapter prose is no longer stored as a flat paragraph blob — it lives in `scenes` + `dialogue_lines` below, so it can be queried per-scene or per-character.

**`scenes`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| chapter_id | uuid FK → chapters | |
| scene_index | int | ordering within the chapter |
| slugline | text | e.g. "INT. SECTOR 4 — ALLEYWAY — NIGHT" |
| action_text | text | scene direction / prose between dialogue |

**`dialogue_lines`** — each character's screenplay for the scene
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| scene_id | uuid FK → scenes | |
| entity_id | uuid FK → entities | who's speaking |
| line_index | int | ordering within the scene |
| parenthetical | text, nullable | e.g. "to himself", "V.O. · fragmented" |
| line | text | the actual dialogue |

**`chapter_user_inputs`** — what the user actually told the story, per chapter
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| chapter_id | uuid FK → chapters | the chapter this input drove |
| arc_id | uuid FK → arcs | |
| selected_choice_id | uuid FK → choices, nullable | set if they picked a preset choice |
| input_text | text | free-text custom action, or a copy of the selected choice's text |

**`choices`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| chapter_id | uuid FK → chapters | |
| text | text | |
| selected | boolean | |
| leads_to_chapter_id | uuid FK → chapters, nullable | |

**`comic_panels`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| chapter_id | uuid FK → chapters | |
| panel_index | int | |
| visual_description | text | |
| camera | text | e.g. "Medium Shot" |
| speech | text, nullable | |
| caption | text, nullable | |
| image_prompt | text, nullable | generated by utility agent |
| image_url | text, nullable | |

### 6.4 Memory

**`character_memory`** — core profile rows (one-ish per character, `memory_type = CORE_PROFILE`) and episodic rows share this table, distinguished by `memory_type`
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| entity_id | uuid FK → entities | |
| memory_type | enum | CORE_PROFILE / EPISODIC / RELATIONSHIP_NOTE / GOAL |
| content | text | |
| importance | smallint | 1–5, set by utility agent on compaction |
| source_chapter_id | uuid FK → chapters, nullable | |
| superseded | boolean | true once folded into a compaction summary row |
| embedding | vector, nullable | unused in v1 |

**`character_screenplay_lines`** — a character's own dialogue history (§4.1), kept separate from `dialogue_lines` because it's a per-character memory view, not the chapter's canonical scene record; populated from `dialogue_lines` at commit time
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| entity_id | uuid FK → entities | |
| dialogue_line_id | uuid FK → dialogue_lines | source row |
| chapter_id | uuid FK → chapters | denormalized for fast "last N for this character" queries |
| chapter_index | int | denormalized, same reason |
| line | text | denormalized copy of the line text |
| embedding | vector, nullable | unused in v1 |

### 6.5 Evaluator & business reports

**`evaluator_reports`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| chapter_id | uuid FK → chapters | |
| overall_status | enum | IN_SYNC / MINOR_DIVERGENCE / MAJOR_DIVERGENCE |

**`evaluator_character_checks`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| evaluator_report_id | uuid FK → evaluator_reports | |
| entity_id | uuid FK → entities | |
| status | enum | IN_SYNC / DIVERGENCE |
| note | text | e.g. "Locked as rule-bound and procedural — this chapter's line reads more casual and taunting than the baseline voice" |

**`evaluator_world_fact_checks`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| evaluator_report_id | uuid FK → evaluator_reports | |
| canon_fact_id | uuid FK → canon_facts, nullable | null if the check is about an unwritten but implied fact |
| label | text | e.g. "Guild masks always ticking" |
| status | enum | IN_SYNC / DIVERGENCE |

**`business_reports`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| chapter_id | uuid FK → chapters | |
| score | smallint | 0–100 overall interest score |
| verdict | text | one-line summary, e.g. "Strong hook, pacing dips mid-arc" |
| note | text | longer-form notes |

**`business_report_breakdown`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| business_report_id | uuid FK → business_reports | |
| label | text | e.g. "Hook strength (Ch1)", "Pacing", "Stakes clarity", "Character likability" |
| score | smallint | 0–100 |

### 6.6 Operational

**`agent_runs`** — observability/debug log, not used for generation itself
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| story_id | uuid FK → stories | |
| chapter_id | uuid FK → chapters, nullable | |
| entity_id | uuid FK → entities, nullable | set for director-agent runs |
| agent_type | enum | ORCHESTRATOR / WORLD / CHARACTER_DIRECTOR / STORYTELLER / EVALUATOR / BUSINESS / UTILITY |
| discussion_round | smallint, nullable | set for director/world runs — which round of the step 5–6 loop this was |
| input_ref | jsonb | pointer/snapshot of what was sent in |
| output | jsonb | |
| status | enum | OK / ADJUSTED / REJECTED / ERROR |
| latency_ms | int | |

**`exports`**
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| story_id | uuid FK → stories | |
| arc_id | uuid FK → arcs, nullable | |
| format | enum | PDF / EPUB / CBZ |
| url | text | |

---

## 7. API surface (mapped to the prototype screens)

| Endpoint | Screen | Notes |
|---|---|---|
| `POST /stories` | Screen 1 | seed type, prompt, genres, tone, art style → triggers utility agent to draft 3 concepts |
| `GET /stories/:id/concepts` | Screen 2 | |
| `POST /stories/:id/concepts/:id/select` | Screen 2 | creates the first `arc` + seed `entities` |
| `GET /arcs/:id/cast` | Screen 3 (cast setup) | predefined entities for this arc, editable while `cast_locked = false` |
| `PATCH /entities/:id` | Screen 3 (cast setup) | edit name/role/voice/traits/visual/hidden_characteristic — rejected once `cast_locked = true` for predefined entities |
| `POST /arcs/:id/cast/lock` | Screen 3 | "Lock cast & launch Chapter 1" — sets `cast_locked = true`, `cast_locked_at = now()` |
| `GET /arcs/:id/state` | Screen 3 (workspace) | current entities + relationships + latest chapter's scenes, for the graph/reader split view; `hidden_characteristic` redacted per entity unless revealed |
| `POST /arcs/:id/chapters/generate` | Screen 3 | runs the full pipeline in §3 |
| `POST /chapters/:id/user-input` | Screen 3 | records free-text custom action → `chapter_user_inputs`, consumed by the next `generate` call |
| `POST /chapters/:id/choices/:id/select` | Screen 3 | resumes pipeline with the chosen branch |
| `GET /chapters/:id/panels` | Screen 4 | |
| `POST /chapters/:id/panels/regenerate` | Screen 4 | utility agent only |
| `GET /arcs/:id/timeline` | Screen 5 | |
| `POST /chapters/:id/export` | Screen 5 | utility agent |
| `GET /arcs/:id/roster` | Screen 6 | predefined entities: status/realm editable always; other fields editable only pre-lock. Introduced entities: fully editable |
| `POST /entities/:id/status` | Screen 6 | direct world-agent write (kill/revive) |
| `POST /entities` | Screen 6 | introduce a new character — direct world-agent write, `introduced_in_chapter_id` set to current chapter |
| `POST /entities/:id/realm` | Screen 6 | change realm — direct world-agent write |
| `POST /arcs/:id/restart` | Screen 6 → 6B | snapshots `arc_carryover`, triggers utility agent for 3 arc-premise options |
| `POST /arcs` | Screen 6B | confirms new arc, launches into workspace |
| `GET /chapters/:id/evaluator-report` | Screen 8 | latest `evaluator_reports` row + checks |
| `GET /chapters/:id/business-report` | Screen 8 | latest `business_reports` row + breakdown |
| `POST /chapters/:id/evaluate` | Screen 8 | "Re-run both agents" — re-runs evaluator + business agents on demand |

---

## 8. Suggested stack

- **API/orchestration layer:** Node (TypeScript) or Python (FastAPI) — either is fine; pick whichever the agent-calling SDK you're using favors.
- **DB:** Postgres (+ `pgvector` extension installed but unused until §4.6 upgrade).
- **Job queue:** for the parallel director-agent fan-out, the discussion-loop retries, and the async utility/evaluator/business-agent tasks — Redis-backed queue (e.g. BullMQ) or a managed equivalent.
- **Agent calls:** each agent = a distinct system prompt + tool access, not a distinct model necessarily. Character director agents can literally be the same model called N times in parallel with different memory context injected. The evaluator and business agents are read-only over the same story data, so they're safe to run with a cheaper/faster model if cost matters more than nuance.

---

## 9. Notes / open questions worth deciding early

- **Parallel director-agent limit:** cap concurrent "active characters per beat" (e.g. 6) — a crowded scene shouldn't mean 20 parallel agent calls.
- **Discussion round budget:** `max_discussion_rounds` defaults to 2 (one initial proposal, one revision after a rejection). Worth watching in practice — too low and the storyteller agent ends up writing around a lot of constrained characters; too high and chapter generation gets slow/expensive.
- **Branch pruning:** unpublished `BRANCH_OPTION` chapters older than N days — auto-archive or keep forever? Affects `chapters`/`scenes`/`dialogue_lines` table growth.
- **Forced reveals:** should an author be able to force-reveal a hidden characteristic from the UI directly (bypassing the storyteller's proposal in step 7), for cases where the auto-generated story never gets around to it? If yes, that's a straightforward direct world-agent write, same shape as Screen 6's kill/revive actions.
- **Evaluator severity → gameplay consequence:** right now a MAJOR_DIVERGENCE finding is purely informational. Worth deciding whether it should ever block chapter publication or just stay a dashboard signal.
