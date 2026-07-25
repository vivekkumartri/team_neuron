"""Template licensing and sponsorship disclosure checks."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from story_engine.domain.policy_models import PolicyDecision, PolicyResult


class TemplateRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10_000)
    license_reference: str | None = Field(default=None, max_length=500)
    sponsor_name: str | None = Field(default=None, max_length=120)
    sponsorship_disclosure: str | None = Field(default=None, max_length=200)


def validate_template(record: TemplateRecord) -> PolicyResult:
    if not record.license_reference:
        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            message="Templates need an original or licensed source record.",
            safe_alternative="Choose an original template or attach its license reference.",
        )
    if record.sponsor_name and not record.sponsorship_disclosure:
        return PolicyResult(
            decision=PolicyDecision.BLOCK,
            message="Sponsored templates require a visible disclosure.",
            safe_alternative="Add a disclosure such as 'Presented by [Brand]'.",
        )
    return PolicyResult(
        decision=PolicyDecision.ALLOW,
        message="Template licensing and disclosure requirements are satisfied.",
    )

