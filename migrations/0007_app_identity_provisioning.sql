BEGIN;

-- The App runtime needs one narrowly scoped, auditable escape hatch to create
-- a tenant before an RLS context exists. All story data remains RLS-protected.
CREATE OR REPLACE FUNCTION app_provision_user(
    p_databricks_user_id TEXT,
    p_email TEXT
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_user_id UUID;
BEGIN
    INSERT INTO users (databricks_user_id, email)
    VALUES (p_databricks_user_id, p_email)
    ON CONFLICT (databricks_user_id) DO UPDATE
        SET email = EXCLUDED.email,
            deleted_at = NULL
    RETURNING id INTO v_user_id;
    RETURN v_user_id;
END;
$$;

COMMIT;
