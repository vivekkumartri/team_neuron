"""Schema/Fact/Passage node models — the memory-graph three-layer shape.

Adapted from MemGraphRAG's `Memory.py` (`SchemaNode`/`FactNode`/`PassageNode`
dataclasses), reshaped as frozen Pydantic models to match this repo's own
`agents/contracts.py` style. Field names track the migration in
`migrations/0023_memory_graph.sql`, not MemGraphRAG's original column names.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchemaCategory(StrEnum):
    ENTITY_TYPE = "ENTITY_TYPE"
    RELATION_TYPE = "RELATION_TYPE"


class FactStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    CONTESTED = "CONTESTED"


class SchemaNode(BaseModel):
    """A single ontology vocabulary entry (an entity type or a relation type).

    Global, non-sensitive, and not branch/character-scoped — see the
    migration's comment on why `schema_nodes` has no RLS.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    category: SchemaCategory
    description: str | None = Field(default=None, max_length=500)


class FactNode(BaseModel):
    """One extracted (head, relation, tail) triple, private to one character.

    Mirrors MemGraphRAG's FactNode triple shape but is always scoped to
    exactly one `branch_id` + `character_id`, per the private-fact-memory
    decision recorded in the migration.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    branch_id: UUID
    character_id: UUID
    head: str = Field(min_length=1, max_length=300)
    head_type: str = Field(min_length=1, max_length=100)
    relation: str = Field(min_length=1, max_length=300)
    relation_type: str = Field(min_length=1, max_length=100)
    tail: str = Field(min_length=1, max_length=300)
    tail_type: str = Field(min_length=1, max_length=100)
    status: FactStatus = FactStatus.ACTIVE
    superseded_by: UUID | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_chapter_id: UUID | None = None
    visible_through_chapter_id: UUID | None = None

    @model_validator(mode="after")
    def _superseded_by_requires_superseded_status(self) -> FactNode:
        if self.superseded_by is not None and self.status is not FactStatus.SUPERSEDED:
            raise ValueError("superseded_by may only be set when status is SUPERSEDED")
        return self

    def as_triple(self) -> tuple[str, str, str]:
        """The bare (head, relation, tail) triple, for candidate/overlap checks."""

        return (self.head, self.relation, self.tail)


class PassageNode(BaseModel):
    """The source text a fact was extracted from — provenance, not memory."""

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    branch_id: UUID
    character_id: UUID
    source_chapter_id: UUID
    text: str = Field(min_length=1, max_length=5_000)
    fact_ids: tuple[UUID, ...] = Field(default=())
