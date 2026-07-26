BEGIN;

-- `generation_events.agent_label`'s CHECK constraint (migration 0005) never
-- included 'character', even though `workers/generation_job.py`'s real
-- agent-coordination loop emits its very first event with
-- `agent="character"` (the character shares their perspective with the
-- Director before Director/World/Storyteller/Evaluator run). Migration 0010
-- added 'character' as a valid *recipient* (`recipient_agent_label`) but
-- never updated this column's own constraint to match — an oversight that
-- was only caught now, running the generation loop end-to-end for the first
-- time (locally): `psycopg.errors.CheckViolation:
-- generation_events_agent_label_check` on the very first `_write_event`
-- call of any generation job.

ALTER TABLE generation_events DROP CONSTRAINT generation_events_agent_label_check;
ALTER TABLE generation_events
    ADD CONSTRAINT generation_events_agent_label_check
    CHECK (agent_label IN ('character', 'world', 'director', 'storyteller', 'evaluator', 'business'));

COMMIT;
