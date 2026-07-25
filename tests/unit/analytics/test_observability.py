"""Task 5I.1 acceptance: a correlated log chain, forbidden-key rejection, and

the per-user budget kill switch — all pure-Python, no live Databricks/Lakebase
connection needed.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from story_engine.analytics.observability import (
    BudgetExceededError,
    BudgetState,
    CorrelatedLogRecord,
    ForbiddenPayloadKeyError,
    MetricEvent,
    emit,
    enforce_budget,
)


def test_correlated_chain_shares_one_id(caplog: pytest.LogCaptureFixture) -> None:
    correlation_id = uuid4()
    with caplog.at_level(logging.INFO, logger="story_engine.observability"):
        emit(CorrelatedLogRecord(correlation_id, MetricEvent.JOB_QUEUE_LATENCY, {"seconds": 1.2}))
        emit(CorrelatedLogRecord(correlation_id, MetricEvent.AGENT_LATENCY, {"seconds": 3.4}))
        emit(
            CorrelatedLogRecord(
                correlation_id, MetricEvent.EVALUATOR_OUTCOME, {"outcome": "APPROVED"}
            )
        )

    ids = {record.correlation_id for record in caplog.records}
    assert ids == {str(correlation_id)}
    events = [record.metric_event for record in caplog.records]
    assert events == ["job_queue_latency", "agent_latency", "evaluator_outcome"]


@pytest.mark.parametrize("forbidden_key", ["prompt", "secret", "hidden_characteristic", "api_key"])
def test_forbidden_payload_key_is_rejected(forbidden_key: str) -> None:
    with pytest.raises(ForbiddenPayloadKeyError):
        emit(
            CorrelatedLogRecord(
                uuid4(), MetricEvent.AGENT_LATENCY, {forbidden_key: "should never be logged"}
            )
        )


def test_budget_under_limit_does_not_raise() -> None:
    enforce_budget(BudgetState(user_id=uuid4(), spend_estimate_usd=1.0, budget_limit_usd=10.0))


def test_budget_at_or_over_limit_raises_and_only_blocks_new_submissions() -> None:
    with pytest.raises(BudgetExceededError) as excinfo:
        enforce_budget(BudgetState(user_id=uuid4(), spend_estimate_usd=10.0, budget_limit_usd=10.0))
    assert "new generation is paused" in str(excinfo.value)
    assert "branches remain available" in str(excinfo.value)
