"""The approved, redacted Delta audit schema — framework-agnostic on purpose.

Kept free of any PySpark import so its forbidden-column contract can be unit
tested without a Spark runtime (this sandbox and most CI runners don't have
one); `export_generation_audit.py` is the only module that touches PySpark.
"""

from __future__ import annotations

# Column name -> SQL type, matching Task 1B.3/3F.3's approved redacted schema.
AUDIT_SCHEMA: dict[str, str] = {
    "job_id": "STRING",
    "tenant_hash": "STRING",
    "branch_id": "STRING",
    "status": "STRING",
    "retry_count": "INT",
    "queue_latency_ms": "BIGINT",
    "generation_latency_ms": "BIGINT",
    "evaluator_outcome": "STRING",
    "model_provider": "STRING",
    "model_version": "STRING",
    "prompt_template_version": "STRING",
    "created_at": "TIMESTAMP",
    "completed_at": "TIMESTAMP",
}

# Anything resembling these must never appear in `AUDIT_SCHEMA` or in a row
# written to the Delta table, regardless of how the schema evolves later.
FORBIDDEN_COLUMN_SUBSTRINGS: tuple[str, ...] = (
    "prose",
    "screenplay",
    "dialogue",
    "prompt_text",
    "raw_prompt",
    "hidden_characteristic",
    "preference",
    "email",
    "user_id",  # only the one-way `tenant_hash` may identify a tenant
    "token",
    "secret",
    "credential",
)


def assert_schema_is_redacted() -> None:
    """Fail fast if a forbidden-shaped column is ever added to AUDIT_SCHEMA."""

    for column in AUDIT_SCHEMA:
        lowered = column.lower()
        for forbidden in FORBIDDEN_COLUMN_SUBSTRINGS:
            if forbidden in lowered:
                raise AssertionError(
                    f"Column {column!r} matches forbidden pattern {forbidden!r}; "
                    "the audit export schema must only contain redacted, non-identifying fields"
                )
