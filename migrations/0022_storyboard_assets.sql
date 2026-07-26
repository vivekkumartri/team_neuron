BEGIN;

-- Public story context used by the storyboard planner. Existing stories use
-- their title as a safe fallback until the author supplies a scenario.
ALTER TABLE stories ADD COLUMN scenario TEXT NOT NULL DEFAULT '';
UPDATE stories SET scenario = title WHERE scenario = '';

ALTER TABLE entities ADD COLUMN background_story TEXT NOT NULL DEFAULT '';
ALTER TABLE entities ADD COLUMN visual_description TEXT NOT NULL DEFAULT '';

CREATE TABLE storyboard_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES stories(id),
    asset_kind TEXT NOT NULL CHECK (asset_kind IN ('CHARACTER_REFERENCE', 'STORYBOARD_PANEL')),
    mime_type TEXT NOT NULL CHECK (mime_type IN ('image/png', 'image/jpeg', 'image/webp')),
    content BYTEA NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE character_visual_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES stories(id),
    entity_id UUID NOT NULL REFERENCES entities(id),
    asset_id UUID NOT NULL REFERENCES storyboard_assets(id),
    source TEXT NOT NULL CHECK (source IN ('UPLOADED', 'GENERATED')),
    reference_prompt TEXT NOT NULL DEFAULT '',
    source_chapter_id UUID REFERENCES chapters(id),
    version INTEGER NOT NULL CHECK (version > 0),
    is_current BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (story_id, entity_id, version)
);
CREATE UNIQUE INDEX character_visual_references_current_idx
    ON character_visual_references(story_id, entity_id) WHERE is_current;

CREATE TABLE storyboard_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID UNIQUE NOT NULL REFERENCES chapters(id),
    requested_by_user_id UUID NOT NULL REFERENCES users(id),
    status TEXT NOT NULL CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE storyboard_scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES storyboard_jobs(id),
    scene_index INTEGER NOT NULL CHECK (scene_index > 0),
    source_line_start INTEGER NOT NULL CHECK (source_line_start > 0),
    source_line_end INTEGER NOT NULL CHECK (source_line_end >= source_line_start),
    character_entity_ids JSONB NOT NULL,
    location TEXT NOT NULL,
    action TEXT NOT NULL,
    emotion TEXT NOT NULL,
    image_prompt TEXT NOT NULL,
    panel_asset_id UUID REFERENCES storyboard_assets(id),
    status TEXT NOT NULL CHECK (status IN ('PLANNED', 'GENERATING', 'SUCCEEDED', 'FAILED')),
    error_message TEXT,
    UNIQUE (job_id, scene_index)
);

ALTER TABLE storyboard_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE character_visual_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE storyboard_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE storyboard_scenes ENABLE ROW LEVEL SECURITY;

CREATE POLICY storyboard_assets_owner ON storyboard_assets
    USING (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()));
CREATE POLICY character_visual_references_owner ON character_visual_references
    USING (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()));
CREATE POLICY storyboard_jobs_owner ON storyboard_jobs
    USING (requested_by_user_id = app_current_user_id())
    WITH CHECK (requested_by_user_id = app_current_user_id());
CREATE POLICY storyboard_scenes_owner ON storyboard_scenes
    USING (EXISTS (
        SELECT 1 FROM storyboard_jobs j
        WHERE j.id = job_id AND j.requested_by_user_id = app_current_user_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM storyboard_jobs j
        WHERE j.id = job_id AND j.requested_by_user_id = app_current_user_id()
    ));

GRANT SELECT, INSERT, UPDATE ON storyboard_assets TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON character_visual_references TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON storyboard_jobs TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON storyboard_scenes TO PUBLIC;

COMMIT;
