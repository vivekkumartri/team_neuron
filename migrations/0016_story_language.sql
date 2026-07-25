BEGIN;

-- Per-story language preference (task.md Phase 6, multilingual support).
-- Scope: story content (generated prose/dialogue/screenplay) and voice
-- (STT hint + TTS) become multilingual. UI chrome stays English regardless
-- of this value. Chosen once at story creation time; not a per-request
-- toggle. Only these three languages are supported in this pass — the
-- CHECK constraint (not a free-text column) is intentional so an invalid
-- code can never reach a row.
ALTER TABLE stories
    ADD COLUMN language TEXT NOT NULL DEFAULT 'en'
    CHECK (language IN ('en', 'hi', 'te'));

COMMIT;
