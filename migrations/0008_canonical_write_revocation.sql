BEGIN;

-- Task 2C.5 gap closed: RLS policies alone only restrict *which rows* a role
-- can see/touch — they do not stop the single Databricks-managed app role
-- (currently the only Postgres role bound to the App's `postgres` resource in
-- resources/app.yml) from writing canon-authoritative tables directly with a
-- plain UPDATE/INSERT/DELETE, bypassing the world-agent commit path entirely.
-- This migration closes that gap the same way `world_publish_chapter`
-- (migration 0006) already does for `chapters`: revoke direct DML on
-- canon-authoritative tables from PUBLIC, and expose narrow SECURITY DEFINER
-- functions as the only write path. SELECT is left untouched — RLS already
-- scopes reads correctly, and read access is not the risk here.
--
-- Director/storyteller/evaluator/business agent code (Task 3E.2) must only
-- ever call these functions (or an equivalent added alongside Task 3E.3/3E.4)
-- to change canon; it must never issue a raw UPDATE against these tables.

REVOKE INSERT, UPDATE, DELETE ON branch_entity_states FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON character_trait_states FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON branch_relationships FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE ON branch_canon_facts FROM PUBLIC;
REVOKE UPDATE, DELETE ON entities FROM PUBLIC;
REVOKE UPDATE, DELETE ON chapters FROM PUBLIC;

-- Staging tables (candidate_chapters, generation_events, agent_runs, reports)
-- deliberately keep normal INSERT rights for the app/job role: they are not
-- canon, and Director/storyteller/evaluator/business agents write to them
-- directly as their proposals/reports are produced (see design.md §5, "Steps
-- 5, 10, and 11 fan out in parallel").

CREATE OR REPLACE FUNCTION world_commit_entity_state(
    p_branch_id UUID,
    p_entity_id UUID,
    p_location_entity_id UUID,
    p_state JSONB
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_next_version INTEGER;
    v_id UUID;
BEGIN
    SELECT COALESCE(MAX(version), 0) + 1 INTO v_next_version
    FROM branch_entity_states WHERE branch_id = p_branch_id AND entity_id = p_entity_id;

    UPDATE branch_entity_states SET is_current = false
    WHERE branch_id = p_branch_id AND entity_id = p_entity_id AND is_current;

    INSERT INTO branch_entity_states (branch_id, entity_id, location_entity_id, state, is_current, version)
    VALUES (p_branch_id, p_entity_id, p_location_entity_id, p_state, true, v_next_version)
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION world_commit_entity_state(UUID, UUID, UUID, JSONB) FROM PUBLIC;

CREATE OR REPLACE FUNCTION world_commit_trait_state(
    p_branch_id UUID,
    p_character_id UUID,
    p_traits JSONB
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_next_version INTEGER;
    v_id UUID;
BEGIN
    SELECT COALESCE(MAX(version), 0) + 1 INTO v_next_version
    FROM character_trait_states WHERE branch_id = p_branch_id AND character_id = p_character_id;

    INSERT INTO character_trait_states (branch_id, character_id, traits, version)
    VALUES (p_branch_id, p_character_id, p_traits, v_next_version)
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION world_commit_trait_state(UUID, UUID, JSONB) FROM PUBLIC;

-- NOTE: world_commit_relationship / world_commit_canon_fact / entity
-- status+realm mutation (kill/revive/move) are intentionally not added yet —
-- they belong with Task 3E.4 (canon-event workflows), which defines the exact
-- validated payload shape each canon-event type accepts. Until those functions
-- exist, `branch_relationships`, `branch_canon_facts`, `entities`, and
-- `chapters` have no INSERT/UPDATE/DELETE path at all for non-owner roles,
-- which is the correct fail-closed default for unfinished write paths.

COMMIT;
