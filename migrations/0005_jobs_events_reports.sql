BEGIN;

CREATE TABLE generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    requested_by_user_id UUID NOT NULL REFERENCES users(id),
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','BLOCKED','CANCELLED')),
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (requested_by_user_id, idempotency_key)
);
CREATE UNIQUE INDEX generation_jobs_one_active_branch_idx ON generation_jobs(branch_id)
    WHERE status IN ('QUEUED', 'RUNNING');

CREATE TABLE generation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES generation_jobs(id),
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    agent_label TEXT NOT NULL CHECK (agent_label IN ('world','director','storyteller','evaluator','business')),
    status TEXT NOT NULL,
    summary TEXT NOT NULL CHECK (char_length(summary) BETWEEN 1 AND 500),
    public_entity_id UUID REFERENCES entities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, sequence)
);

CREATE TABLE candidate_chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID UNIQUE NOT NULL REFERENCES generation_jobs(id),
    branch_id UUID NOT NULL REFERENCES branches(id),
    focal_character_id UUID NOT NULL REFERENCES entities(id),
    screenplay JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('STAGED','APPROVED','REJECTED','BLOCKED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES generation_jobs(id),
    agent_label TEXT NOT NULL,
    status TEXT NOT NULL,
    redacted_summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE evaluator_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID UNIQUE NOT NULL REFERENCES candidate_chapters(id),
    outcome TEXT NOT NULL CHECK (outcome IN ('APPROVED','MINOR_DIVERGENCE','MAJOR_DIVERGENCE','FAILED')),
    redacted_summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE business_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID UNIQUE NOT NULL REFERENCES candidate_chapters(id),
    disclosed_weighting JSONB NOT NULL DEFAULT '{}'::jsonb,
    redacted_summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type TEXT NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX outbox_unpublished_idx ON outbox(created_at) WHERE published_at IS NULL;

COMMIT;
