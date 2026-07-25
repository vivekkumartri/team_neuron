BEGIN;

-- Task 2C.2 named these among its target tables but they were not created in
-- migration 0003; added here alongside Task 3E.4, which is the first task
-- that actually needs them.

CREATE TABLE canon_event_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    requested_by_user_id UUID NOT NULL REFERENCES users(id),
    event_type TEXT NOT NULL CHECK (event_type IN ('KILL', 'REVIVE', 'MOVE_REALM', 'INTRODUCE_ENTITY', 'EDIT_CANON')),
    target_entity_id UUID REFERENCES entities(id),
    proposed_payload JSONB NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','EVALUATING','APPROVED','ADJUSTED','REJECTED','FAILED')),
    evaluator_report_id UUID,
    world_decision TEXT,
    committed_canon_event_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX canon_event_requests_branch_idx ON canon_event_requests(branch_id);

-- Append-only audit of committed direct canon events (distinct from
-- branch_canon_facts, which is the queryable current-lore ledger).
CREATE TABLE canon_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    effective_after_chapter_id UUID REFERENCES chapters(id),
    event_type TEXT NOT NULL,
    before_state JSONB NOT NULL,
    after_state JSONB NOT NULL,
    source_request_id UUID REFERENCES canon_event_requests(id),
    committed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE canon_event_requests
    ADD CONSTRAINT canon_event_requests_committed_fk
    FOREIGN KEY (committed_canon_event_id) REFERENCES canon_events(id);

-- Author-requested screenplay/content edits after publication. An approved
-- revision always points at a replacement branch; the original chapter row
-- is never mutated (design.md "Author Edits and Canon-Event Requests").
CREATE TABLE chapter_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapters(id),
    requested_by_user_id UUID NOT NULL REFERENCES users(id),
    author_patch TEXT NOT NULL,
    evaluator_report_id UUID,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','EVALUATING','APPROVED','REJECTED','FAILED')),
    replacement_branch_id UUID REFERENCES branches(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (status != 'APPROVED' OR replacement_branch_id IS NOT NULL)
);
CREATE INDEX chapter_revisions_chapter_idx ON chapter_revisions(chapter_id);

-- One row per generated ending candidate for a branch; distinct from
-- `choices`, which drives ordinary chapter-to-chapter progression.
CREATE TABLE ending_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id),
    label TEXT NOT NULL,
    summary TEXT NOT NULL,
    selected BOOLEAN NOT NULL DEFAULT false,
    resulting_chapter_id UUID REFERENCES chapters(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ending_options_one_selected_idx ON ending_options(branch_id) WHERE selected;

ALTER TABLE canon_event_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE canon_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapter_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ending_options ENABLE ROW LEVEL SECURITY;

CREATE POLICY canon_event_requests_owner ON canon_event_requests
    USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY canon_events_owner ON canon_events
    USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY chapter_revisions_owner ON chapter_revisions
    USING (EXISTS (SELECT 1 FROM chapters c JOIN branches b ON b.id = c.branch_id JOIN stories s ON s.id = b.story_id WHERE c.id = chapter_id AND s.user_id = app_current_user_id()));
CREATE POLICY ending_options_owner ON ending_options
    USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));

-- Only the world-command path may commit a canon event or approve a
-- revision; the API/agent roles get ordinary RLS-scoped INSERT (to create a
-- *request*, status DRAFT) but never write `canon_events` or flip a request
-- straight to APPROVED themselves.
REVOKE INSERT, UPDATE, DELETE ON canon_events FROM PUBLIC;

CREATE OR REPLACE FUNCTION world_commit_canon_event(
    p_request_id UUID,
    p_after_state JSONB
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_branch_id UUID;
    v_before_state JSONB;
    v_event_type TEXT;
    v_event_id UUID;
BEGIN
    SELECT branch_id, event_type, proposed_payload INTO v_branch_id, v_event_type, v_before_state
    FROM canon_event_requests WHERE id = p_request_id AND status = 'EVALUATING';

    IF v_branch_id IS NULL THEN
        RAISE EXCEPTION 'canon event request % is not eligible for commit', p_request_id;
    END IF;

    INSERT INTO canon_events (branch_id, event_type, before_state, after_state, source_request_id)
    VALUES (v_branch_id, v_event_type, v_before_state, p_after_state, p_request_id)
    RETURNING id INTO v_event_id;

    UPDATE canon_event_requests
    SET status = 'APPROVED', committed_canon_event_id = v_event_id
    WHERE id = p_request_id;

    RETURN v_event_id;
END;
$$;

REVOKE ALL ON FUNCTION world_commit_canon_event(UUID, JSONB) FROM PUBLIC;

COMMIT;
