BEGIN;

-- "No one is Protagonist" — every character in a story's cast is now
-- treated uniformly; there is no special role that can't be removed and no
-- character that generation privileges over any other. `cast_members.role`
-- previously distinguished 'PROTAGONIST' (immutable, always focal-first) from
-- 'SUPPORTING'. Collapse both into a single 'CHARACTER' value.

-- Drop the old constraint FIRST — it only allowed 'PROTAGONIST'/'SUPPORTING',
-- so backfilling to 'CHARACTER' while it's still active fails with
-- `CheckViolation` (caught running this the first time).
ALTER TABLE cast_members DROP CONSTRAINT IF EXISTS cast_members_role_check;
ALTER TABLE cast_members ALTER COLUMN role SET DEFAULT 'CHARACTER';
UPDATE cast_members SET role = 'CHARACTER' WHERE role IN ('PROTAGONIST', 'SUPPORTING');
ALTER TABLE cast_members ADD CONSTRAINT cast_members_role_check CHECK (role = 'CHARACTER');

COMMIT;
