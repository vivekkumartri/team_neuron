BEGIN;

CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    rights_basis TEXT NOT NULL CHECK (rights_basis IN ('original', 'licensed')),
    license_reference TEXT NOT NULL,
    source_attribution TEXT NOT NULL,
    approved_scene_map JSONB NOT NULL,
    sponsorship_disclosure TEXT,
    approved_at TIMESTAMPTZ NOT NULL,
    archived_at TIMESTAMPTZ
);

CREATE TABLE branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES stories(id),
    arc_id UUID NOT NULL REFERENCES arcs(id),
    parent_branch_id UUID REFERENCES branches(id),
    forked_from_chapter_id UUID,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'PAUSED', 'COMPLETED', 'ARCHIVED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (story_id, name)
);

CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES stories(id),
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('character', 'location', 'faction', 'object')),
    founding_branch_id UUID REFERENCES branches(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (story_id, name)
);

CREATE TABLE branch_entity_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    entity_id UUID NOT NULL REFERENCES entities(id),
    location_entity_id UUID REFERENCES entities(id),
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_current BOOLEAN NOT NULL DEFAULT true,
    version INTEGER NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (branch_id, entity_id, version)
);
CREATE UNIQUE INDEX branch_entity_current_idx ON branch_entity_states(branch_id, entity_id) WHERE is_current;

CREATE TABLE character_trait_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    character_id UUID NOT NULL REFERENCES entities(id),
    traits JSONB NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (branch_id, character_id, version)
);

CREATE TABLE branch_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    from_entity_id UUID NOT NULL REFERENCES entities(id),
    to_entity_id UUID NOT NULL REFERENCES entities(id),
    relationship_type TEXT NOT NULL,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (branch_id, from_entity_id, to_entity_id, relationship_type, version)
);

CREATE TABLE branch_canon_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    subject_entity_id UUID REFERENCES entities(id),
    fact_key TEXT NOT NULL,
    fact_value JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retired_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX branch_canon_current_idx ON branch_canon_facts(branch_id, subject_entity_id, fact_key) WHERE retired_at IS NULL;

CREATE TABLE world_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    chapter_id UUID,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    chapter_index INTEGER NOT NULL CHECK (chapter_index > 0),
    focal_character_id UUID NOT NULL REFERENCES entities(id),
    focal_trait_state_id UUID REFERENCES character_trait_states(id),
    status TEXT NOT NULL CHECK (status IN ('DRAFT','QUEUED','GENERATING','EVALUATING','PUBLISHED','BLOCKED','FAILED','ARCHIVED')),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (branch_id, chapter_index)
);
ALTER TABLE branches ADD CONSTRAINT branches_fork_chapter_fk FOREIGN KEY (forked_from_chapter_id) REFERENCES chapters(id);
ALTER TABLE world_snapshots ADD CONSTRAINT world_snapshots_chapter_fk FOREIGN KEY (chapter_id) REFERENCES chapters(id);

CREATE TABLE scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapters(id),
    scene_index INTEGER NOT NULL CHECK (scene_index > 0),
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (chapter_id, scene_index)
);
CREATE TABLE dialogue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID NOT NULL REFERENCES scenes(id),
    line_index INTEGER NOT NULL CHECK (line_index > 0),
    speaker_entity_id UUID REFERENCES entities(id),
    line_text TEXT NOT NULL,
    UNIQUE (scene_id, line_index)
);
CREATE TABLE choices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapters(id),
    choice_index INTEGER NOT NULL CHECK (choice_index BETWEEN 1 AND 3),
    label TEXT NOT NULL,
    progression_mode TEXT NOT NULL CHECK (progression_mode IN ('CONTINUE','EDIT_TRAITS','REWIND')),
    UNIQUE (chapter_id, choice_index)
);

CREATE INDEX branches_story_id_idx ON branches(story_id) WHERE archived_at IS NULL;
CREATE INDEX chapters_branch_id_idx ON chapters(branch_id);

COMMIT;
