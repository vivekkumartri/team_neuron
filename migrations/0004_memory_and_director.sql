BEGIN;

CREATE TABLE story_directors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID UNIQUE NOT NULL REFERENCES branches(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE character_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    character_id UUID NOT NULL REFERENCES entities(id),
    memory_kind TEXT NOT NULL CHECK (memory_kind IN ('CORE', 'EPISODIC', 'SCREENPLAY')),
    content JSONB NOT NULL,
    source_chapter_id UUID REFERENCES chapters(id),
    visible_through_chapter_id UUID REFERENCES chapters(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX character_memories_lookup_idx ON character_memories(branch_id, character_id, memory_kind);

CREATE TABLE director_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    director_id UUID NOT NULL REFERENCES story_directors(id),
    memory_kind TEXT NOT NULL CHECK (memory_kind IN ('STRATEGY', 'DECISION', 'OPEN_THREAD')),
    summary TEXT NOT NULL CHECK (char_length(summary) BETWEEN 1 AND 1000),
    source_chapter_id UUID REFERENCES chapters(id),
    visible_through_chapter_id UUID REFERENCES chapters(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (summary !~* '(hidden characteristic|private memory|private excerpt|unrevealed secret)')
);
CREATE INDEX director_memories_lookup_idx ON director_memories(director_id, memory_kind);

COMMIT;
