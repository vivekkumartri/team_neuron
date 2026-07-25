BEGIN;

ALTER TABLE canon_event_requests ADD COLUMN idempotency_key TEXT;
CREATE UNIQUE INDEX canon_event_requests_requester_idempotency_idx
    ON canon_event_requests (requested_by_user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

COMMIT;
