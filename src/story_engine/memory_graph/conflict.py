"""Conflict detection over fact-layer triples, ported from MemGraphRAG's idea.

MemGraphRAG's own conflict search assumes an embedding index
(`fact_embedding_store`) to find candidate fact pairs before running an LLM
classification step over each pair. team_neuron has no embedding/vector
infra today (integration plan Section 3 flags this as an open decision), so
`find_candidate_pairs` here is a cheap entity/keyword-overlap filter instead:
two ACTIVE facts for the same character are only worth an LLM call if they
share a head or a tail string. This keeps Session 3 shippable without adding
new infrastructure; swapping in an embedding-backed candidate search later
only changes `find_candidate_pairs`, not `classify_conflict` or the
`WorldAgent` integration.

The three conflict categories (mutual / temporal / granularity) are
MemGraphRAG's own taxonomy for how two facts about the same subject can
disagree:
  - MUTUAL: the two facts are flatly incompatible (Mira owns the key vs.
    Mira lost the key, both stated as currently true).
  - TEMPORAL: both facts can be true, but at different points in the story
    (Mira owned the key, then gave it away) — the earlier one should be
    superseded, not treated as contradictory.
  - GRANULARITY: one fact is a more specific/general restatement of the
    other, not a real disagreement (Mira owns a key vs. Mira owns a bronze
    key).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, ValidationError

from story_engine.agents.prompts.system import COMMON_BOUNDARY, PROMPT_VERSION
from story_engine.agents.provider import ModelProvider
from story_engine.memory_graph.schema import FactNode, FactStatus
from story_engine.security.prompt_safety import delimit_untrusted_text


class ConflictCategory(StrEnum):
    MUTUAL = "MUTUAL"
    TEMPORAL = "TEMPORAL"
    GRANULARITY = "GRANULARITY"


class ConflictResolutionAction(StrEnum):
    # The earlier fact (by source_chapter_id ordering, provided by the
    # caller) is superseded by the later one.
    SUPERSEDE_EARLIER = "SUPERSEDE_EARLIER"
    # Both facts stand; the "conflict" was only a granularity mismatch.
    KEEP_BOTH = "KEEP_BOTH"
    # A real, unresolved mutual contradiction — WorldAgent's FLAG_CONTINUITY
    # is the right outcome; a human/service reviews it.
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"


class ConflictResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: ConflictCategory
    action: ConflictResolutionAction
    rationale: str


CONFLICT_CLASSIFY_SYSTEM_PROMPT = (
    f"ConflictClassify {PROMPT_VERSION}: You are given two candidate facts about the "
    "same character, each as a (head, relation, tail) triple. Decide whether they "
    "conflict, and if so how. Respond with ONLY a JSON object (no prose, no markdown "
    'fences) with exactly these keys: "category" (one of "MUTUAL", "TEMPORAL", '
    '"GRANULARITY"), "action" (one of "SUPERSEDE_EARLIER", "KEEP_BOTH", '
    '"FLAG_FOR_REVIEW"), and "rationale" (a one-sentence explanation, under 200 '
    "characters). Use MUTUAL+FLAG_FOR_REVIEW when the facts flatly contradict each "
    "other with no clear resolution. Use TEMPORAL+SUPERSEDE_EARLIER when the second "
    "fact is a later update that replaces the first. Use GRANULARITY+KEEP_BOTH when "
    f"the facts are compatible restatements at different specificity. {COMMON_BOUNDARY}"
)


def _shares_subject(fact_a: FactNode, fact_b: FactNode) -> bool:
    a_terms = {fact_a.head.strip().casefold(), fact_a.tail.strip().casefold()}
    b_terms = {fact_b.head.strip().casefold(), fact_b.tail.strip().casefold()}
    return bool(a_terms & b_terms)


def find_candidate_pairs(
    facts: Sequence[FactNode],
) -> tuple[tuple[FactNode, FactNode], ...]:
    """Cheap keyword-overlap candidate filter (see module docstring).

    Only ACTIVE facts for a single character/branch are considered — callers
    are expected to have already scoped `facts` to one `(branch_id,
    character_id)` pair, the same isolation boundary `character_memories`
    and `context_assembler.py` already enforce.
    """

    active = [fact for fact in facts if fact.status is FactStatus.ACTIVE]
    pairs: list[tuple[FactNode, FactNode]] = []
    for i, fact_a in enumerate(active):
        for fact_b in active[i + 1 :]:
            if fact_a.relation.strip().casefold() == fact_b.relation.strip().casefold():
                # Identical relation is handled as an exact duplicate, not a
                # conflict worth an LLM call.
                if fact_a.as_triple() == fact_b.as_triple():
                    continue
            if _shares_subject(fact_a, fact_b):
                pairs.append((fact_a, fact_b))
    return tuple(pairs)


def _describe_fact(fact: FactNode) -> str:
    return f"({fact.head}, {fact.relation}, {fact.tail})"


def classify_conflict(
    provider: ModelProvider,
    *,
    model: str,
    fact_a: FactNode,
    fact_b: FactNode,
) -> ConflictResult:
    """Run the LLM classification step over one candidate fact pair."""

    passage = (
        f"Fact 1 (earlier): {_describe_fact(fact_a)}\n"
        f"Fact 2 (later): {_describe_fact(fact_b)}"
    )
    raw_response = provider.complete(
        system_prompt=CONFLICT_CLASSIFY_SYSTEM_PROMPT,
        user_data=delimit_untrusted_text(passage, source="conflict_classify"),
        model=model,
    )
    candidate = raw_response.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise ValueError("Conflict classification response was not valid JSON") from error
    try:
        return ConflictResult.model_validate(parsed)
    except ValidationError as error:
        raise ValueError("Conflict classification response was malformed") from error


def detect_conflicts(
    provider: ModelProvider,
    *,
    model: str,
    facts: Sequence[FactNode],
) -> tuple[tuple[FactNode, FactNode, ConflictResult], ...]:
    """Find candidate pairs and classify each one. One classification call per pair."""

    results: list[tuple[FactNode, FactNode, ConflictResult]] = []
    for fact_a, fact_b in find_candidate_pairs(facts):
        result = classify_conflict(provider, model=model, fact_a=fact_a, fact_b=fact_b)
        if result.category is not ConflictCategory.GRANULARITY:
            results.append((fact_a, fact_b, result))
        elif result.action is not ConflictResolutionAction.KEEP_BOTH:
            # A granularity mismatch should normally resolve to KEEP_BOTH;
            # surface anything that didn't, since that's an unexpected model
            # response worth a human/service look, not a silent drop.
            results.append((fact_a, fact_b, result))
    return tuple(results)


def facts_requiring_continuity_flag(
    conflicts: Iterable[tuple[FactNode, FactNode, ConflictResult]],
) -> tuple[tuple[FactNode, FactNode, ConflictResult], ...]:
    """Filter conflicts down to the ones WorldAgent should raise FLAG_CONTINUITY for."""

    return tuple(
        conflict
        for conflict in conflicts
        if conflict[2].action is ConflictResolutionAction.FLAG_FOR_REVIEW
    )
