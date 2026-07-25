BEGIN;

ALTER TABLE generation_events ADD COLUMN recipient_agent_label TEXT;
ALTER TABLE generation_events
    ADD CONSTRAINT generation_events_recipient_agent_label_check
    CHECK (
        recipient_agent_label IS NULL OR recipient_agent_label IN
        ('world', 'director', 'storyteller', 'evaluator', 'business', 'character')
    );

-- The request owner may write and inspect the durable outbox item associated
-- with their own job. The dispatcher still controls delivery; this policy
-- lets the API record the request atomically under RLS.
DROP POLICY IF EXISTS outbox_owner ON outbox;
CREATE POLICY outbox_owner ON outbox
    USING (
        EXISTS (
            SELECT 1 FROM generation_jobs j
            WHERE j.id = aggregate_id AND j.requested_by_user_id = app_current_user_id()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM generation_jobs j
            WHERE j.id = aggregate_id AND j.requested_by_user_id = app_current_user_id()
        )
    );

CREATE OR REPLACE FUNCTION world_publish_generated_candidate(
    p_job_id UUID,
    p_candidate_id UUID
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_branch_id UUID;
    v_focal_character_id UUID;
    v_screenplay JSONB;
    v_chapter_id UUID;
    v_chapter_index INTEGER;
BEGIN
    SELECT j.branch_id, c.focal_character_id, c.screenplay
    INTO v_branch_id, v_focal_character_id, v_screenplay
    FROM generation_jobs j
    JOIN candidate_chapters c ON c.job_id = j.id
    WHERE j.id = p_job_id
      AND c.id = p_candidate_id
      AND c.status = 'APPROVED'
      AND j.requested_by_user_id = app_current_user_id();

    IF NOT FOUND THEN
        RAISE EXCEPTION 'approved candidate is not available to this user';
    END IF;

    SELECT COALESCE(MAX(chapter_index), 0) + 1 INTO v_chapter_index
    FROM chapters WHERE branch_id = v_branch_id;

    INSERT INTO chapters (branch_id, chapter_index, focal_character_id, status, published_at)
    VALUES (v_branch_id, v_chapter_index, v_focal_character_id, 'PUBLISHED', now())
    RETURNING id INTO v_chapter_id;

    INSERT INTO scenes (chapter_id, scene_index, summary)
    VALUES (v_chapter_id, 1, COALESCE(v_screenplay->>'screenplay', ''));

    INSERT INTO choices (chapter_id, choice_index, label, progression_mode) VALUES
        (v_chapter_id, 1, 'Continue automatically', 'CONTINUE'),
        (v_chapter_id, 2, 'Edit traits', 'EDIT_TRAITS'),
        (v_chapter_id, 3, 'Jump / rewind', 'REWIND');

    RETURN v_chapter_id;
END;
$$;

-- The function checks the caller's tenant context and candidate/job ownership;
-- no application role receives direct chapter DML privileges.
GRANT EXECUTE ON FUNCTION world_publish_generated_candidate(UUID, UUID) TO PUBLIC;

COMMIT;
