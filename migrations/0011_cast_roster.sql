BEGIN;

CREATE TABLE cast_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES stories(id),
    entity_id UUID NOT NULL REFERENCES entities(id),
    role TEXT NOT NULL DEFAULT 'SUPPORTING' CHECK (role IN ('PROTAGONIST', 'SUPPORTING')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (story_id, entity_id)
);

ALTER TABLE stories ADD COLUMN cast_locked_at TIMESTAMPTZ;

ALTER TABLE cast_members ENABLE ROW LEVEL SECURITY;
CREATE POLICY cast_members_owner ON cast_members
    USING (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()));

COMMIT;
