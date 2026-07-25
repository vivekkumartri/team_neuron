BEGIN;

CREATE OR REPLACE FUNCTION app_current_user_id() RETURNS UUID
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE personalization_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE stories ENABLE ROW LEVEL SECURITY;
ALTER TABLE arcs ENABLE ROW LEVEL SECURITY;
ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE branch_entity_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE character_trait_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE branch_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE branch_canon_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE scenes ENABLE ROW LEVEL SECURITY;
ALTER TABLE dialogue ENABLE ROW LEVEL SECURITY;
ALTER TABLE choices ENABLE ROW LEVEL SECURITY;
ALTER TABLE story_directors ENABLE ROW LEVEL SECURITY;
ALTER TABLE character_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE director_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluator_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_owner ON users USING (id = app_current_user_id()) WITH CHECK (id = app_current_user_id());
CREATE POLICY preferences_owner ON user_preferences USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id());
CREATE POLICY snapshots_owner ON personalization_snapshots USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id());
CREATE POLICY stories_owner ON stories USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id());
CREATE POLICY arcs_owner ON arcs USING (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()));
CREATE POLICY branches_owner ON branches USING (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()));
CREATE POLICY entities_owner ON entities USING (EXISTS (SELECT 1 FROM stories s WHERE s.id = story_id AND s.user_id = app_current_user_id()));
CREATE POLICY branch_entity_states_owner ON branch_entity_states USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY trait_states_owner ON character_trait_states USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY relationships_owner ON branch_relationships USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY canon_facts_owner ON branch_canon_facts USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY snapshots_branch_owner ON world_snapshots USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY chapters_owner ON chapters USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY scenes_owner ON scenes USING (EXISTS (SELECT 1 FROM chapters c JOIN branches b ON b.id = c.branch_id JOIN stories s ON s.id = b.story_id WHERE c.id = chapter_id AND s.user_id = app_current_user_id()));
CREATE POLICY dialogue_owner ON dialogue USING (EXISTS (SELECT 1 FROM scenes sc JOIN chapters c ON c.id = sc.chapter_id JOIN branches b ON b.id = c.branch_id JOIN stories s ON s.id = b.story_id WHERE sc.id = scene_id AND s.user_id = app_current_user_id()));
CREATE POLICY choices_owner ON choices USING (EXISTS (SELECT 1 FROM chapters c JOIN branches b ON b.id = c.branch_id JOIN stories s ON s.id = b.story_id WHERE c.id = chapter_id AND s.user_id = app_current_user_id()));
CREATE POLICY directors_owner ON story_directors USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY character_memories_owner ON character_memories USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY director_memories_owner ON director_memories USING (EXISTS (SELECT 1 FROM story_directors d JOIN branches b ON b.id = d.branch_id JOIN stories s ON s.id = b.story_id WHERE d.id = director_id AND s.user_id = app_current_user_id()));
CREATE POLICY jobs_owner ON generation_jobs USING (requested_by_user_id = app_current_user_id());
CREATE POLICY events_owner ON generation_events USING (EXISTS (SELECT 1 FROM generation_jobs j WHERE j.id = job_id AND j.requested_by_user_id = app_current_user_id()));
CREATE POLICY candidates_owner ON candidate_chapters USING (EXISTS (SELECT 1 FROM branches b JOIN stories s ON s.id = b.story_id WHERE b.id = branch_id AND s.user_id = app_current_user_id()));
CREATE POLICY agent_runs_owner ON agent_runs USING (EXISTS (SELECT 1 FROM generation_jobs j WHERE j.id = job_id AND j.requested_by_user_id = app_current_user_id()));
CREATE POLICY evaluator_reports_owner ON evaluator_reports USING (EXISTS (SELECT 1 FROM candidate_chapters c JOIN branches b ON b.id = c.branch_id JOIN stories s ON s.id = b.story_id WHERE c.id = candidate_id AND s.user_id = app_current_user_id()));
CREATE POLICY business_reports_owner ON business_reports USING (EXISTS (SELECT 1 FROM candidate_chapters c JOIN branches b ON b.id = c.branch_id JOIN stories s ON s.id = b.story_id WHERE c.id = candidate_id AND s.user_id = app_current_user_id()));
CREATE POLICY outbox_owner ON outbox USING (false);

CREATE OR REPLACE FUNCTION world_publish_chapter(p_chapter_id UUID) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM chapters WHERE id = p_chapter_id AND status = 'EVALUATING') THEN
    RAISE EXCEPTION 'chapter is not eligible for publication';
  END IF;
  UPDATE chapters SET status = 'PUBLISHED', published_at = now() WHERE id = p_chapter_id;
END;
$$;

REVOKE ALL ON FUNCTION world_publish_chapter(UUID) FROM PUBLIC;

COMMIT;
