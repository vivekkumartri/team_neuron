BEGIN;

ALTER TABLE chapters ADD COLUMN archived_at TIMESTAMPTZ;

-- migration 0008 revoked direct UPDATE on `chapters` from PUBLIC, so
-- archive/unarchive (like every other canon mutation in this schema) goes
-- through a narrow SECURITY DEFINER function rather than a plain UPDATE.
CREATE OR REPLACE FUNCTION world_set_chapter_archived(
    p_chapter_id UUID,
    p_archived BOOLEAN
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_id UUID;
BEGIN
    UPDATE chapters c
    SET archived_at = CASE WHEN p_archived THEN now() ELSE NULL END
    FROM branches b, stories s
    WHERE c.id = p_chapter_id
      AND b.id = c.branch_id
      AND s.id = b.story_id
      AND s.user_id = app_current_user_id()
    RETURNING c.id INTO v_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'chapter not found or not owned by caller';
    END IF;

    RETURN v_id;
END;
$$;

GRANT EXECUTE ON FUNCTION world_set_chapter_archived(UUID, BOOLEAN) TO PUBLIC;

COMMIT;
