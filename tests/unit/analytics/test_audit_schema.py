from __future__ import annotations

from story_engine.analytics.audit_schema import assert_schema_is_redacted
from story_engine.analytics.export_generation_audit import hash_tenant_id


def test_approved_schema_has_no_forbidden_columns() -> None:
    assert_schema_is_redacted()  # raises AssertionError on failure


def test_tenant_hash_is_deterministic_and_does_not_reveal_the_user_id() -> None:
    hashed = hash_tenant_id("user-123", salt="test-salt")
    assert hashed != "user-123"
    assert hash_tenant_id("user-123", salt="test-salt") == hashed
    assert hash_tenant_id("user-123", salt="different-salt") != hashed
