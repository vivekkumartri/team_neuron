BEGIN;

-- Adapts MemGraphRAG's (schema -> fact -> passage) three-layer memory shape
-- (see docs/adr/0001-memgraphrag-adaptation.md) into this repo's own memory
-- model. It is deliberately NOT vendoring MemGraphRAG's `Memory.py` runtime;
-- these tables mirror the *idea* (SchemaNode/FactNode/PassageNode) with
-- team_neuron's own branch/character isolation and RLS conventions, the same
-- way `character_memories` (migration 0004) already scopes flat memory.
--
-- Decision recorded here (integration plan Section 3, "private vs shared
-- fact memory"): fact-layer entries are per-character-private, matching
-- today's isolation model (`character_memories`), NOT branch-shared like
-- `director_memories`. Rationale: the fact layer is populated from a single
-- character's episodic memory during extraction (Session 2), and
-- `context_assembler.py`'s `ContextAssemblyError` already treats
-- cross-character leakage as a hard boundary (Session 4 extends, not
-- relaxes, that boundary). Branch-shared canon facts already have a home
-- (`branch_canon_facts`, migration 0003); this is not that.

-- schema_nodes is a small, non-sensitive ontology vocabulary (type names
-- like 'Character' or relation names like 'owns'), not tenant-private data,
-- so it is a global lookup table -- same pattern as `templates`, which
-- migration 0006 never enabled RLS on and 0017 grants plain SELECT for.
CREATE TABLE schema_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100),
    category TEXT NOT NULL CHECK (category IN ('ENTITY_TYPE', 'RELATION_TYPE')),
    description TEXT CHECK (description IS NULL OR char_length(description) <= 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, category)
);

-- fact_nodes: one extracted (head, relation, tail) triple, scoped and
-- isolated exactly like character_memories rows are today.
CREATE TABLE fact_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    character_id UUID NOT NULL REFERENCES entities(id),
    head TEXT NOT NULL CHECK (char_length(head) BETWEEN 1 AND 300),
    head_type TEXT NOT NULL CHECK (char_length(head_type) BETWEEN 1 AND 100),
    relation TEXT NOT NULL CHECK (char_length(relation) BETWEEN 1 AND 300),
    relation_type TEXT NOT NULL CHECK (char_length(relation_type) BETWEEN 1 AND 100),
    tail TEXT NOT NULL CHECK (char_length(tail) BETWEEN 1 AND 300),
    tail_type TEXT NOT NULL CHECK (char_length(tail_type) BETWEEN 1 AND 100),
    -- ACTIVE: currently believed true. SUPERSEDED: replaced by a newer fact
    -- (superseded_by points at it) after conflict resolution. CONTESTED:
    -- WorldAgent (conflict.py, Session 3) flagged a contradiction that has
    -- not yet been resolved -- distinct from SUPERSEDED, which already has
    -- a resolution.
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'CONTESTED')),
    superseded_by UUID REFERENCES fact_nodes(id),
    confidence REAL CHECK (confidence IS NULL OR (confidence BETWEEN 0 AND 1)),
    source_chapter_id UUID REFERENCES chapters(id),
    visible_through_chapter_id UUID REFERENCES chapters(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (superseded_by IS NULL OR status = 'SUPERSEDED')
);
-- Read path (context_assembler.py, Session 4): fetch a focal character's
-- ACTIVE facts on a branch.
CREATE INDEX fact_nodes_lookup_idx ON fact_nodes(branch_id, character_id, status);
-- Candidate-pair path (conflict.py, Session 3): this repo has no embedding
-- index today (integration plan Section 3, "embedding infra" is an open
-- decision), so conflict detection starts from a cheap entity/keyword
-- overlap filter on head/tail text rather than a vector search.
CREATE INDEX fact_nodes_candidate_idx ON fact_nodes(branch_id, character_id, head, tail)
    WHERE status = 'ACTIVE';

-- passage_nodes: the source text a fact was extracted from, kept for
-- provenance/audit (mirrors MemGraphRAG's PassageNode).
CREATE TABLE passage_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    character_id UUID NOT NULL REFERENCES entities(id),
    source_chapter_id UUID NOT NULL REFERENCES chapters(id),
    text TEXT NOT NULL CHECK (char_length(text) BETWEEN 1 AND 5000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX passage_nodes_lookup_idx ON passage_nodes(branch_id, character_id, source_chapter_id);

CREATE TABLE fact_passage_links (
    fact_id UUID NOT NULL REFERENCES fact_nodes(id) ON DELETE CASCADE,
    passage_id UUID NOT NULL REFERENCES passage_nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (fact_id, passage_id)
);

ALTER TABLE fact_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE passage_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_passage_links ENABLE ROW LEVEL SECURITY;

-- Same owner-derivation shape as `character_memories_owner` (migration
-- 0006): branch -> story -> user_id.
CREATE POLICY fact_nodes_owner ON fact_nodes
    USING (EXISTS (
        SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id
        WHERE b.id = branch_id AND s.user_id = app_current_user_id()
    ));
CREATE POLICY passage_nodes_owner ON passage_nodes
    USING (EXISTS (
        SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id
        WHERE b.id = branch_id AND s.user_id = app_current_user_id()
    ));
CREATE POLICY fact_passage_links_owner ON fact_passage_links
    USING (EXISTS (
        SELECT 1 FROM fact_nodes f
        JOIN branches b ON b.id = f.branch_id
        JOIN stories s ON s.id = b.story_id
        WHERE f.id = fact_id AND s.user_id = app_current_user_id()
    ));

-- Grants combined into this same migration (unlike the historical
-- 0006/0017 split, which only happened because 0017 was a bugfix for
-- tables 0006 had already shipped without grants) -- these tables are new,
-- so there is no reason to repeat that gap here.
GRANT SELECT, INSERT ON schema_nodes TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fact_nodes TO PUBLIC;
GRANT SELECT, INSERT ON passage_nodes TO PUBLIC;
GRANT SELECT, INSERT ON fact_passage_links TO PUBLIC;

COMMIT;
