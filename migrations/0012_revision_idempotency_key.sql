BEGIN;

ALTER TABLE chapter_revisions ADD COLUMN idempotency_key TEXT;
CREATE UNIQUE INDEX chapter_revisions_requester_idempotency_idx
    ON chapter_revisions (requested_by_user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

COMMIT;
