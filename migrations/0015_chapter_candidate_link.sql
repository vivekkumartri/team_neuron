BEGIN;

-- Task 3F.1 report_job wiring gap: `report_job.run_report_job(chapter_id)` needs
-- a deterministic path from a published chapter back to the `candidate_chapters`
-- row (and, from there, the `generation_jobs` row) that produced it — nothing
-- in `chapters` recorded that link before this migration.
ALTER TABLE chapters ADD COLUMN candidate_id UUID REFERENCES candidate_chapters(id);
CREATE INDEX chapters_candidate_id_idx ON chapters(candidate_id) WHERE candidate_id IS NOT NULL;

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

    INSERT INTO chapters (branch_id, chapter_index, focal_character_id, status, published_at, candidate_id)
    VALUES (v_branch_id, v_chapter_index, v_focal_character_id, 'PUBLISHED', now(), p_candidate_id)
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

GRANT EXECUTE ON FUNCTION world_publish_generated_candidate(UUID, UUID) TO PUBLIC;

COMMIT;
