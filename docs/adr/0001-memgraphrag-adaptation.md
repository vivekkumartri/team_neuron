# ADR 0001 — Adapting MemGraphRAG's memory-graph idea, not vendoring the repo

**Status:** Accepted
**Date:** 2026-07-26
**Related:** `memgraphrag-integration-plan.md` (integration plan this ADR is Session 5 of)

## Context

We wanted MemGraphRAG's schema→fact→passage memory-graph idea and its
mutual/temporal/granularity conflict detection inside team_neuron's
character memory system (`persistence/memory.py`, `character_memories`,
`agents/context_assembler.py`).

## What we found when we checked the actual repo (not just its README)

- The MemGraphRAG README documents an API surface —
  `entity_type_extract.py`, `schema_fact_extract.py`, `llm_client.py`,
  `prompt_builder.py`, `ontology_filtering.py`, `resolve_conflict.py` at the
  repo root — that **does not exist** in the shipped code. The real tree is
  `code/src/MemGraphRAG.py`, `code/src/Memory.py`, `code/index.py`, plus
  `code/src/{information_extraction,llm,embedding_model,prompts,evaluation,utils}/`.
- The README claims spaCy `en_core_web_trf` NER; `requirements.txt` has no
  spaCy. The real pipeline is LLM-based OpenIE
  (`information_extraction/openie_openai.py`) or offline vLLM OpenIE
  (`openie_vllm_offline.py`).
- It's a benchmark/research pipeline for HotpotQA / 2WikiMultihopQA /
  MuSiQue / medical QA, forked/derived from HippoRAG (a stray
  `__pycache__/HippoRAG.*.pyc` confirms this). `requirements.txt` pulls
  `vllm==0.6.6.post1`, `torch==2.5.1`, `transformers==4.45.2`, `gritlm`,
  `python_igraph` — a GPU-oriented offline-indexing stack, not something to
  `pip install` into a Databricks App / FastAPI request-serving process.
- License is MIT (Xiamen University DeepLIT Group, 2026) — reuse/adaptation
  is fine; verbatim-ported structure should keep an attribution note (see
  below).

## Decision

We did **not** add MemGraphRAG as a dependency. We reimplemented the one
genuinely portable piece — `Memory.py`'s `ThreeLayerMemory` shape
(`SchemaNode` / `FactNode` / `PassageNode`, plain JSON-serializable
dataclasses) and the mutual/temporal/granularity conflict-detection
*idea* — from scratch, against this repo's own `ModelProvider` protocol
(`agents/provider.py`) and Lakebase Postgres, following the same
frozen-Pydantic/branch-and-character-scoped-RLS conventions
`agents/contracts.py`, `persistence/memory.py`, and
`migrations/0004_memory_and_director.sql` already use.

A future session must not reintroduce `vllm`/`torch`/`gritlm`/spaCy to
"align more closely with upstream" — that stack does not fit this
deployment (`RuntimeSettings`, `lakebase_connection`, the Databricks App
runtime have no GPU, no local model weights, and no offline-batch execution
model).

## What was built (Sessions 1–5)

| Session | Files | Decision recorded here |
| --- | --- | --- |
| 1 — Data model | `migrations/0023_memory_graph.sql`, `memory_graph/schema.py` | **Private vs. shared fact memory:** fact-layer entries are per-character-private (`branch_id` + `character_id` scoped, RLS via `branches → stories → user_id`, same as `character_memories`), not branch-shared like `director_memories`. `schema_nodes` (the type vocabulary) is a global, non-RLS lookup table, same pattern as `templates`. |
| 2 — Relation extraction | `memory_graph/relation_extract.py` | Triple extraction is a JSON-only prompt through `ModelProvider.complete`, not a schema-constrained tool call (the provider protocol doesn't support one) — parsed defensively, one malformed triple doesn't discard the rest of a passage. |
| 3 — Conflict detection | `memory_graph/conflict.py`, `agents/world.py` | **Embedding infra:** team_neuron has none today, so candidate fact pairs are found via a cheap entity/keyword-overlap filter (shared head/tail text) instead of MemGraphRAG's embedding-index candidate search. Swapping in a real embedding search later only changes `find_candidate_pairs`. `WorldAgent.action()` is unchanged; `find_continuity_conflicts()` is additive. |
| 4 — Context assembly | `agents/contracts.py`, `agents/context_assembler.py` | Top-k ACTIVE facts are merged into `CharacterMemoryBuckets.facts`, additive alongside the existing `episodic` tuple, not replacing it. `assemble_character_context` raises `ContextAssemblyError` if fact input isn't already scoped to the focal character's branch — it does not silently filter, matching the file's existing "raise, don't leak" posture. |
| 5 — Indexing job | `workers/memory_graph_index.py`, `resources/jobs.yml`, `pyproject.toml` | Runs as a post-chapter-publication Databricks Job (`memory_graph_index_job`), registered exactly like `memory_compaction_job`. Not inline on the request path. |

## Verification status (honesty note, per `task.md`'s own convention)

- Sessions 1–4 have unit tests (`tests/unit/memory_graph/`,
  `tests/unit/agents/test_world_conflict.py`,
  `tests/unit/agents/test_context_assembler_graph.py`) that were run in
  this sandbox with `pytest`; all pass, including every pre-existing
  `tests/unit/agents/` test unchanged.
- Session 5's `workers/memory_graph_index.py` SQL is hand-reviewed against
  the real schema but **has not been executed against a live
  Lakebase/Postgres workspace** — this sandbox has no `psycopg` or
  `databricks-sdk` installed to connect with. Before relying on this in
  production: run `databricks bundle validate -t dev`, then a real
  dev-workspace invocation of `memory_graph_index_job` against a branch
  with actual episodic memory.

## Attribution

`memory_graph/schema.py`'s `SchemaNode`/`FactNode`/`PassageNode` shape and
`memory_graph/conflict.py`'s conflict taxonomy are adapted from
XMUDeepLIT/MemGraphRAG (MIT License, 2026) —
https://github.com/XMUDeepLIT/MemGraphRAG. No code was copied verbatim;
field names, validation, and persistence are this repo's own.
