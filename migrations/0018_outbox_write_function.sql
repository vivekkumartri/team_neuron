BEGIN;

-- Task: fix live "Couldn't lock the cast" failure. `0017`'s
-- `outbox_insert_by_job_owner` RLS policy (an INSERT `WITH CHECK` containing
-- an `EXISTS (... generation_jobs ...)` subquery) still rejects the
-- request-time INSERT from `progression.py`/`workers/outbox.py` in the live
-- Databricks App with `psycopg.errors.InsufficientPrivilege: new row
-- violates row-level security policy for table "outbox"`, even though the
-- same connection/transaction just successfully inserted the owning
-- `generation_jobs` row moments earlier. Since this environment's Postgres
-- role, RLS-context propagation, and prepared-statement/session behavior
-- can't currently be inspected with a live `psql` session, we stop relying
-- on a client-role RLS policy to gate this specific write and instead adopt
-- this codebase's existing canonical pattern for exactly this situation
-- (see migration 0008's `world_commit_entity_state`/`world_commit_trait_state`,
-- and 0010/0013/0015's `world_publish_generated_candidate`/
-- `world_set_chapter_archived`): a narrow `SECURITY DEFINER` function that
-- performs the ownership check and the INSERT in one atomic, RLS-independent
-- step. `SECURITY DEFINER` functions run with the function owner's
-- privileges, so they are not subject to the calling role's RLS policies at
-- all -- only to the ownership check written explicitly in the function
-- body below, which enforces the exact same invariant the old policy meant
-- to: an outbox row may only be created for a `generation_jobs` row the
-- current tenant (`app_current_user_id()`) actually owns.

CREATE OR REPLACE FUNCTION world_write_outbox_entry(
    p_aggregate_type TEXT,
    p_aggregate_id UUID,
    p_event_type TEXT,
    p_payload JSONB
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_id UUID;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM generation_jobs j
        WHERE j.id = p_aggregate_id AND j.requested_by_user_id = app_current_user_id()
    ) THEN
        RAISE EXCEPTION
            'outbox entry must reference a generation_jobs row owned by the current user'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload)
    VALUES (p_aggregate_type, p_aggregate_id, p_event_type, p_payload)
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

-- Called directly from request-time routes (progression.py), same as
-- world_publish_generated_candidate/world_set_chapter_archived -- so, like
-- those, PUBLIC gets EXECUTE.
GRANT EXECUTE ON FUNCTION world_write_outbox_entry(TEXT, UUID, TEXT, JSONB) TO PUBLIC;

-- The function is now the only end-user write path into outbox; a direct
-- client-role INSERT is no longer needed and is removed so there is exactly
-- one way to create a row, matching the canon-write-path convention.
DROP POLICY IF EXISTS outbox_insert_by_job_owner ON outbox;
REVOKE INSERT ON outbox FROM PUBLIC;

COMMIT;
