"""Structured, redacted application logging and metrics.

Every emitted record carries a correlation id and passes through
`_assert_no_forbidden_keys` before it's logged — the same "redact by
default" posture as `ClientGenerationEvent` (domain/events.py) and
`AUDIT_SCHEMA` (analytics/audit_schema.py), just applied to the operational
telemetry surface instead of the client SSE stream or the Delta export.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

logger = logging.getLogger("story_engine.observability")

# Keys that must never appear in a metric/log payload, regardless of caller
# intent — mirrors `FORBIDDEN_COLUMN_SUBSTRINGS` in audit_schema.py so the two
# redaction boundaries (Delta export, operational logs) can't silently drift
# apart from each other.
FORBIDDEN_PAYLOAD_KEYS: tuple[str, ...] = (
    "prompt",
    "secret",
    "hidden_characteristic",
    "preference_value",
    "raw_response",
    "api_key",
)


class MetricEvent(StrEnum):
    JOB_QUEUE_LATENCY = "job_queue_latency"
    AGENT_LATENCY = "agent_latency"
    RETRY_COUNT = "retry_count"
    EVALUATOR_OUTCOME = "evaluator_outcome"
    SSE_RECONNECT = "sse_reconnect"
    RLS_DENIAL = "rls_denial"
    DEPLOYMENT_VERSION = "deployment_version"
    MODEL_SPEND_ESTIMATE = "model_spend_estimate"
    BUDGET_THRESHOLD_EXCEEDED = "budget_threshold_exceeded"
    CHAPTER_LOOP_COMPLETION = "chapter_loop_completion"
    BRANCH_CREATED = "branch_created"
    TRAIT_EDIT_ACCEPTANCE = "trait_edit_acceptance"
    ENDING_OPTION_USE = "ending_option_use"
    COMIC_EXPORT_PLACEHOLDER = "comic_export_placeholder"


class ForbiddenPayloadKeyError(ValueError):
    """A metric/log call attempted to include a key that must never be logged."""


def _assert_no_forbidden_keys(payload: dict[str, Any]) -> None:
    lowered_keys = {key.lower() for key in payload}
    for forbidden in FORBIDDEN_PAYLOAD_KEYS:
        if forbidden in lowered_keys:
            raise ForbiddenPayloadKeyError(
                f"Refusing to log payload containing forbidden key {forbidden!r}"
            )


@dataclass(frozen=True)
class CorrelatedLogRecord:
    """One entry in a correlated chain — a job's queue-latency, agent-latency,

    and evaluator-outcome events all share `correlation_id` so a single
    generation attempt can be reconstructed from logs without touching
    Lakebase.
    """

    correlation_id: UUID
    event: MetricEvent
    payload: dict[str, Any] = field(default_factory=dict)


def emit(record: CorrelatedLogRecord) -> None:
    _assert_no_forbidden_keys(record.payload)
    logger.info(
        "story_engine_metric",
        extra={
            "correlation_id": str(record.correlation_id),
            "metric_event": record.event.value,
            **record.payload,
        },
    )


# --- Per-user budget kill switch -------------------------------------------


@dataclass(frozen=True)
class BudgetState:
    user_id: UUID
    spend_estimate_usd: float
    budget_limit_usd: float


class BudgetExceededError(RuntimeError):
    """Raised when a new generation submission would exceed the user's budget.

    Existing in-flight jobs are never cancelled by this check — it only ever
    blocks *new* submissions, per Task 5I.1's "pauses new generation
    submissions with a clear message" requirement.
    """


def enforce_budget(state: BudgetState) -> None:
    if state.spend_estimate_usd < state.budget_limit_usd:
        return
    emit(
        CorrelatedLogRecord(
            correlation_id=state.user_id,
            event=MetricEvent.BUDGET_THRESHOLD_EXCEEDED,
            payload={
                "spend_estimate_usd": state.spend_estimate_usd,
                "budget_limit_usd": state.budget_limit_usd,
            },
        )
    )
    raise BudgetExceededError(
        "You've reached your generation budget for this period. Existing chapters and "
        "branches remain available; new generation is paused until the next period or a "
        "budget increase."
    )
