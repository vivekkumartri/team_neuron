"""LLM triple extraction via `agents/provider.py::ModelProvider`.

Reimplements MemGraphRAG's extraction *prompt strategy* — pull
`(head, relation, tail)` triples with `(head_type, relation_type, tail_type)`
out of a passage — as a JSON-only call through the provider this repo
already has (`ModelProvider.complete`). No spaCy, no vLLM, no gritlm: see
`docs/adr/0001-memgraphrag-adaptation.md` for why those were left behind.

`ModelProvider.complete` returns free text, not a schema-constrained
response, so the system prompt instructs the model to return *only* JSON and
`_parse_triples` defensively parses it — the same defensive-JSON posture
`provider.py::_extract_response_text` already takes with the raw Responses
API payload.
"""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError

from story_engine.agents.contracts import CharacterMemoryBuckets
from story_engine.agents.prompts.system import COMMON_BOUNDARY, PROMPT_VERSION
from story_engine.agents.provider import ModelProvider, ModelProviderError
from story_engine.memory_graph.schema import FactNode
from story_engine.security.prompt_safety import delimit_untrusted_text

RELATION_EXTRACT_SYSTEM_PROMPT = (
    f"RelationExtract {PROMPT_VERSION}: Read the untrusted passage and extract every "
    "clear (head, relation, tail) fact it states about the focal character. "
    "Respond with ONLY a JSON array (no prose, no markdown fences). Each array "
    "element must be an object with exactly these string keys: "
    '"head", "head_type", "relation", "relation_type", "tail", "tail_type", '
    'and a "confidence" number between 0 and 1. If the passage states no clear '
    "facts, respond with exactly []. "
    f"{COMMON_BOUNDARY}"
)

MAX_TRIPLES_PER_PASSAGE = 20


class RelationExtractionError(RuntimeError):
    """Raised when the provider's response cannot be parsed into fact triples."""


def _parse_triples(raw_response: str) -> list[dict[str, object]]:
    """Defensively parse a model response that should be a bare JSON array.

    Models occasionally wrap JSON in markdown fences despite instructions;
    strip those before parsing rather than failing on the first attempt.
    """

    candidate = raw_response.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise RelationExtractionError("Model response was not valid JSON") from error

    if not isinstance(parsed, list):
        raise RelationExtractionError("Model response was not a JSON array")
    return [item for item in parsed if isinstance(item, dict)]


def extract_facts_from_passage(
    provider: ModelProvider,
    *,
    model: str,
    branch_id: UUID,
    character_id: UUID,
    passage_text: str,
    source_chapter_id: UUID | None = None,
    visible_through_chapter_id: UUID | None = None,
) -> tuple[FactNode, ...]:
    """Extract fact-layer triples from one passage for one character.

    Mirrors `ProposalAgent.propose`'s untrusted-data delimiting instead of
    subclassing it: this is a data-extraction call, not an agent proposal
    (`AgentProposal`'s `ProposalAction` enum has no extraction action, and
    extraction output isn't reviewed/committed by a service the way agent
    proposals are).
    """

    try:
        raw_response = provider.complete(
            system_prompt=RELATION_EXTRACT_SYSTEM_PROMPT,
            user_data=delimit_untrusted_text(passage_text, source="relation_extract"),
            model=model,
        )
    except ModelProviderError:
        raise

    triples = _parse_triples(raw_response)[:MAX_TRIPLES_PER_PASSAGE]

    facts: list[FactNode] = []
    for triple in triples:
        try:
            facts.append(
                FactNode(
                    branch_id=branch_id,
                    character_id=character_id,
                    head=str(triple["head"]),
                    head_type=str(triple["head_type"]),
                    relation=str(triple["relation"]),
                    relation_type=str(triple["relation_type"]),
                    tail=str(triple["tail"]),
                    tail_type=str(triple["tail_type"]),
                    confidence=_coerce_confidence(triple.get("confidence")),
                    source_chapter_id=source_chapter_id,
                    visible_through_chapter_id=visible_through_chapter_id,
                )
            )
        except (KeyError, ValidationError, TypeError, ValueError):
            # One malformed triple should not discard the rest of a passage's
            # otherwise-valid facts.
            continue
    return tuple(facts)


def _coerce_confidence(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def passage_text_from_episodic_memory(memory: CharacterMemoryBuckets, *, limit: int = 10) -> str:
    """Join a character's most recent episodic entries into one extraction passage.

    Bounded to `limit` entries so a single extraction call stays well inside
    the passage-size assumptions the prompt above makes (`passage_nodes.text`
    is itself capped at 5,000 chars by the migration).
    """

    return "\n".join(memory.episodic[-limit:])
