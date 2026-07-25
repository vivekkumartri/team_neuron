BEGIN;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    databricks_user_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    preference_key TEXT NOT NULL,
    preference_value JSONB NOT NULL,
    source TEXT NOT NULL,
    consented_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, preference_key)
);

CREATE TABLE personalization_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    snapshot_version INTEGER NOT NULL CHECK (snapshot_version > 0),
    preferences JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, snapshot_version)
);

CREATE TABLE stories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    personalization_enabled BOOLEAN NOT NULL DEFAULT false,
    personalization_snapshot_id UUID REFERENCES personalization_snapshots(id),
    agent_trace_enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CHECK (personalization_enabled OR personalization_snapshot_id IS NULL)
);

CREATE TABLE arcs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES stories(id),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (story_id, name, version)
);

CREATE INDEX user_preferences_user_id_idx ON user_preferences(user_id);
CREATE INDEX personalization_snapshots_user_id_idx ON personalization_snapshots(user_id);
CREATE INDEX stories_user_id_idx ON stories(user_id) WHERE deleted_at IS NULL;
CREATE INDEX arcs_story_id_idx ON arcs(story_id) WHERE archived_at IS NULL;

COMMIT;
