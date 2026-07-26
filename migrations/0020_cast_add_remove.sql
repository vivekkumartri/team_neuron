BEGIN;

-- Task: mid-story cast add/remove. `cast_members` only had SELECT, INSERT
-- granted (migration 0017) — enough to lock the initial cast, but with no
-- way to ever remove a member afterward. `cast_members_owner`'s RLS policy
-- (migration 0011) has no FOR clause, so it already applies its USING
-- expression to DELETE too; only the table-level GRANT was missing.
GRANT DELETE ON cast_members TO PUBLIC;

COMMIT;
