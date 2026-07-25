BEGIN;

-- Migration 0006 enabled RLS and created owner policies on every user-scoped
-- table, but never GRANTed the underlying table-level privileges those
-- policies filter. RLS policies only restrict which ROWS a role can see once
-- it already has permission to touch the table at all; without a base GRANT,
-- every query fails with a flat "permission denied for table ..." regardless
-- of RLS. Postgres grants EXECUTE on new FUNCTIONS to PUBLIC by default
-- (which is why app_provision_user/world_commit_* worked fine and JIT user
-- provisioning succeeded), but it never does this for TABLES — that
-- asymmetry is exactly why this went unnoticed through every prior
-- migration-runner-as-superuser test and only surfaced once the live
-- Databricks App connected as its own (non-owner) Postgres role: a real
-- 500 on GET /api/v1/me/preferences, "permission denied for table
-- user_preferences".
--
-- This grants the same baseline every one of these tables always needed,
-- while deliberately NOT re-granting anything migrations 0008/0009 already
-- revoked from PUBLIC on purpose (branch_entity_states,
-- character_trait_states, branch_relationships, branch_canon_facts,
-- canon_events stay write-locked to their SECURITY DEFINER commit
-- functions; entities/chapters stay UPDATE/DELETE-locked the same way).

GRANT SELECT ON templates TO PUBLIC;

GRANT SELECT, INSERT, UPDATE ON users TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_preferences TO PUBLIC;
GRANT SELECT, INSERT ON personalization_snapshots TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON stories TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON arcs TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON branches TO PUBLIC;

-- Canonical world-state tables: grant only what 0008 did NOT revoke.
GRANT SELECT, INSERT ON entities TO PUBLIC;
GRANT SELECT ON branch_entity_states TO PUBLIC;
GRANT SELECT ON character_trait_states TO PUBLIC;
GRANT SELECT ON branch_relationships TO PUBLIC;
GRANT SELECT ON branch_canon_facts TO PUBLIC;
GRANT SELECT, INSERT ON world_snapshots TO PUBLIC;
GRANT SELECT, INSERT ON chapters TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON scenes TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON dialogue TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON choices TO PUBLIC;

GRANT SELECT, INSERT, UPDATE ON story_directors TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON character_memories TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON director_memories TO PUBLIC;

GRANT SELECT, INSERT, UPDATE ON generation_jobs TO PUBLIC;
GRANT SELECT, INSERT ON generation_events TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON candidate_chapters TO PUBLIC;
GRANT SELECT, INSERT ON agent_runs TO PUBLIC;
GRANT SELECT, INSERT ON evaluator_reports TO PUBLIC;
GRANT SELECT, INSERT ON business_reports TO PUBLIC;

-- canon_events itself stays write-locked per 0009's own revocation (written
-- only via world_commit_canon_event); the request/tracking tables around it
-- are normal owner-scoped tables and need the usual grant.
GRANT SELECT, INSERT, UPDATE ON canon_event_requests TO PUBLIC;
GRANT SELECT ON canon_events TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON chapter_revisions TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON ending_options TO PUBLIC;

GRANT SELECT, INSERT ON cast_members TO PUBLIC;

-- outbox needed more than a grant: 0006's blanket `USING (false)` policy
-- made it impossible for ANY connection to ever INSERT a row, including
-- progression.py's own same-transaction write -- the one thing this table
-- exists for. Replace it with two narrow, purpose-built policies: an
-- end-user request may INSERT an outbox row only for a generation_jobs row
-- it owns (mirrors the existing jobs_owner check), and the background
-- dispatcher (job_dispatcher.dispatch_pending — see workers/outbox.py and
-- services/job_dispatcher.py, which never call set_tenant_context, so
-- app.user_id is unset on that connection) may SELECT/UPDATE any row. An
-- ordinary per-request connection (which always has app.user_id set) still
-- cannot read or update outbox rows directly — matching the original
-- intent that end users never see the outbox, just no longer at the cost
-- of breaking the one legitimate write path into it.
GRANT SELECT, INSERT, UPDATE ON outbox TO PUBLIC;
DROP POLICY IF EXISTS outbox_owner ON outbox;

CREATE POLICY outbox_insert_by_job_owner ON outbox
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM generation_jobs j
            WHERE j.id = aggregate_id AND j.requested_by_user_id = app_current_user_id()
        )
    );

CREATE POLICY outbox_system_dispatch_select ON outbox
    FOR SELECT
    USING (current_setting('app.user_id', true) IS NULL);

CREATE POLICY outbox_system_dispatch_update ON outbox
    FOR UPDATE
    USING (current_setting('app.user_id', true) IS NULL);

COMMIT;
