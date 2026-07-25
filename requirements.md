# Story Engine — Product Requirements

## Product Goal

Create a desktop-first, responsive, multi-user web application where every author privately builds AI-assisted, branching stories. Each story has one owner in MVP. The MVP is text-first and produces structured scenes and character dialogue.

## Core Experience

1. The author starts with a custom prompt, dream fragment, partial narrative, or preset.
2. The system generates three story concepts for selection and optional editing.
3. The author defines a founding cast, then locks it.
4. Locking the cast immediately starts Chapter 1 generation.
5. The workspace first shows a loader, then streams an interactive, safe summary of agent discussion and progressively renders the chapter.
6. Generated chapters are automatically published only after world validation and evaluator approval.
7. After each chapter, the author selects exactly one progression mode: Continue automatically, Edit traits, or Jump/rewind. Approved trait edits and rewinds create parallel branches; all branches are retained forever and can be archived, never deleted.

## Agent and Canon Requirements

- The world agent is the sole authority that commits canonical state.
- One branch Director proposes actions for multiple characters through isolated per-character calls; the storyteller writes scenes and dialogue.
- The evaluator checks consistency. A major divergence blocks publication, warns the author, and triggers bounded automatic regeneration.
- The business agent produces post-publication narrative-interest analysis; its failure must not unpublish a valid chapter.
- Authors can submit canon-event requests (for example, kill, revive, move, or introduce a character). The evaluator reviews them and the world agent makes the final commit/adjust/reject decision.
- Hidden characteristics must be completely absent from user-facing UI, APIs, traces, graph, roster, and reports until the story reveals them. Direct forced reveal is not available in MVP.

## User Personalization and Isolation

- Every user has completely separate stories, character memory, Director memory, world state, agent runs, reports, and personalization profile. No data or memory may be shared across users.
- Collect optional, consented preferences such as favorite genres, tones, pacing, themes, interaction style, accessibility settings, and content boundaries.
- Preferences are user-editable, deletable, exportable, and can be disabled globally or per story.
- Personalization is not story canon and must never be copied into character memory or Director memory.
- Use only an approved, versioned personalization snapshot for a generation. Do not collect sensitive personal data for MVP or use inferred preferences without explicit opt-in.

## MVP Scope

- Multi-user platform with one private owner per story.
- FastAPI in Databricks Apps, Next.js/React frontend, Tailwind CSS, Lakebase Postgres, Databricks Jobs, and Unity Catalog/Delta audit storage.
- Read-only entity relationship graph with accessible list alternatives.
- Responsive layouts, with desktop as the primary authoring experience.
- Configurable font family/text scale and accessible non-color-only states.
- Author-redacted agent-run trace is available only when the story trace flag is enabled.

## Initial Configurable Limits

| Setting | Default |
| --- | ---: |
| Active characters per beat | 4 |
| Discussion rounds | 2 |
| Generation retry attempts | 3 |
| Automatic evaluator regenerations | 2 |
| Seed prompt length | Up to 2,000 characters; inputs below ~12 tokens open a visible clarification loop, never a hard block |
| Minimum chapters before manual ending request | 3 |
| Storyteller narrative directions | 2 (advisory only; not progression modes) |
| Concurrent generation jobs per user | 2 |
| Chapter generations per user per day | 20 |
| Automatic ending pacing threshold | 0.75 configured ending-readiness score |
| Regressive trait-edit nudge threshold | 3 requests in a rolling 10-chapter window |
| Per-user daily model-token budget | 250,000 input + output tokens |

## Deferred

- Collaboration roles
- Image/comic generation, animated portraits, and media exports
- User self-avatar / “insert yourself” character
- Vector/RAG retrieval
