"""Story REST endpoints with RLS-scoped queries."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from story_engine.agents.provider import ModelProviderError, OpenAIResponsesProvider
from story_engine.api.auth import AuthenticatedUser, authenticate_request, tenant_connection
from story_engine.api.settings import load_settings
from story_engine.domain.models import StoryLanguage
from story_engine.domain.policy_models import PolicyDecision, PolicySubject
from story_engine.security.content_policy import RuleBasedContentPolicy
from story_engine.services.cast_proposal import (
    CastCharacterProposal,
    CastProposalError,
    propose_cast,
)

router = APIRouter(prefix="/api/v1/stories", tags=["stories"])
CurrentUser = Annotated[AuthenticatedUser, Depends(authenticate_request)]


class CastMemberInput(BaseModel):
    """One author-edited character from the cast-setup UI.

    Deliberately has no `hidden`/secret field (task.md 0.4 — the
    prototype's blurred hidden-characteristic row is explicitly not
    ported). Every field here is exactly what the author saw and could
    edit in `CastLock.tsx`.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default="", max_length=120)
    voice: str = Field(default="", max_length=200)
    traits: str = Field(default="", max_length=200)
    visual: str = Field(default="", max_length=200)
    is_protagonist: bool = False


class CastProposalInput(BaseModel):
    """Uncommitted seed data used to generate an editable starting cast."""

    model_config = ConfigDict(extra="forbid")

    seed: str = Field(min_length=1, max_length=2_000)
    language: StoryLanguage = StoryLanguage.ENGLISH


class CastProposalResponse(BaseModel):
    characters: list[CastCharacterProposal]


class StoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    personalization_enabled: bool = False
    agent_trace_enabled: bool = False
    # Per-story preference, chosen once at creation (task.md Phase 6
    # multilingual entry) — not a per-request toggle. Pydantic validates
    # against the enum, so an unsupported code (e.g. "fr") is rejected with
    # a 422 rather than silently defaulting to English.
    language: StoryLanguage = StoryLanguage.ENGLISH
    # Optional full edited cast from the cast-setup screen (task.md Task
    # 4H.2 gap closure). When omitted/empty, behavior is unchanged from
    # before: a single "Protagonist" entity is created (see below).
    cast: list[CastMemberInput] = Field(default_factory=list, max_length=6)


class StoryResponse(BaseModel):
    id: UUID
    title: str
    personalization_enabled: bool
    agent_trace_enabled: bool
    language: StoryLanguage
    initial_branch_id: UUID | None = None
    initial_focal_entity_id: UUID | None = None


def _story_response(row: object) -> StoryResponse:
    values = cast(tuple[object, ...], row)
    return StoryResponse(
        id=UUID(str(values[0])),
        title=str(values[1]),
        personalization_enabled=bool(values[2]),
        agent_trace_enabled=bool(values[3]),
        language=StoryLanguage(str(values[4])),
        initial_branch_id=(
            UUID(str(values[5])) if len(values) > 5 and values[5] is not None else None
        ),
        initial_focal_entity_id=(
            UUID(str(values[6])) if len(values) > 6 and values[6] is not None else None
        ),
    )


@router.get("", response_model=list[StoryResponse])
def list_stories(user: CurrentUser) -> list[StoryResponse]:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT s.id, s.title, s.personalization_enabled, s.agent_trace_enabled, "
                "s.language, "
                "(SELECT b.id FROM branches b WHERE b.story_id=s.id AND b.archived_at IS NULL "
                " ORDER BY b.created_at LIMIT 1), "
                "(SELECT e.id FROM entities e WHERE e.story_id=s.id AND e.entity_type='character' "
                " ORDER BY e.created_at LIMIT 1) "
                "FROM stories s WHERE s.deleted_at IS NULL ORDER BY s.created_at DESC"
            )
            rows = cursor.fetchall()
    return [_story_response(row) for row in rows]


@router.post("/cast-proposal", response_model=CastProposalResponse)
def create_cast_proposal(payload: CastProposalInput, user: CurrentUser) -> CastProposalResponse:
    """Generate a safe, author-editable cast without persisting any character."""

    del user  # Authentication is required, but a proposal has no database write.
    policy_result = RuleBasedContentPolicy().assess(payload.seed, PolicySubject.SEED)
    if policy_result.decision is not PolicyDecision.ALLOW:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": policy_result.message,
                "safe_alternative": policy_result.safe_alternative,
            },
        )

    settings = load_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Character generation is not configured yet.",
        )
    try:
        characters = propose_cast(
            provider=OpenAIResponsesProvider(api_key=settings.openai_api_key),
            model=settings.openai_model,
            seed=payload.seed,
            language=payload.language,
        )
    except (CastProposalError, ModelProviderError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate a character proposal. Please try again.",
        ) from error
    return CastProposalResponse(characters=characters)


@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
def create_story(payload: StoryInput, user: CurrentUser) -> StoryResponse:
    with tenant_connection(user) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO stories (user_id, title, personalization_enabled, "
                "agent_trace_enabled, language) "
                "VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id, title, personalization_enabled, agent_trace_enabled, language",
                (
                    user.id,
                    payload.title,
                    payload.personalization_enabled,
                    payload.agent_trace_enabled,
                    payload.language.value,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Story creation failed"
                )
            values = cast(tuple[object, ...], row)
            story_id = UUID(str(values[0]))
            cursor.execute(
                "INSERT INTO arcs (story_id, name) VALUES (%s, 'Main arc') RETURNING id",
                (story_id,),
            )
            arc_id = UUID(str(cast(tuple[object, ...], cursor.fetchone())[0]))
            cursor.execute(
                "INSERT INTO branches (story_id, arc_id, name, status) "
                "VALUES (%s, %s, 'Main timeline', 'ACTIVE') RETURNING id",
                (story_id, arc_id),
            )
            branch_id = UUID(str(cast(tuple[object, ...], cursor.fetchone())[0]))

            cast_input = payload.cast
            focal_id: UUID | None = None
            if cast_input:
                # One `entities` row per author-edited character, not just a
                # single hardcoded protagonist (task.md Task 4H.2 gap
                # closure). The protagonist-flagged character is always
                # inserted FIRST regardless of its position in the payload,
                # so it is also the "earliest created character entity" that
                # `list_stories` and `cast.py`'s lock-cast role assignment
                # both use as their focal/protagonist signal — no separate
                # `is_protagonist` column needed on `entities`.
                protagonist_index = next(
                    (i for i, member in enumerate(cast_input) if member.is_protagonist), 0
                )
                ordered_cast = [cast_input[protagonist_index]] + [
                    member for i, member in enumerate(cast_input) if i != protagonist_index
                ]
                for index, member in enumerate(ordered_cast):
                    cursor.execute(
                        "INSERT INTO entities (story_id, name, entity_type, founding_branch_id) "
                        "VALUES (%s, %s, 'character', %s) RETURNING id",
                        (story_id, member.name, branch_id),
                    )
                    entity_id = UUID(str(cast(tuple[object, ...], cursor.fetchone())[0]))
                    if index == 0:
                        focal_id = entity_id
            else:
                cursor.execute(
                    "INSERT INTO entities (story_id, name, entity_type, founding_branch_id) "
                    "VALUES (%s, 'Protagonist', 'character', %s) RETURNING id",
                    (story_id, branch_id),
                )
                focal_id = UUID(str(cast(tuple[object, ...], cursor.fetchone())[0]))
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Story creation failed"
        )
    return StoryResponse(
        id=story_id,
        title=str(values[1]),
        personalization_enabled=bool(values[2]),
        agent_trace_enabled=bool(values[3]),
        language=StoryLanguage(str(values[4])),
        initial_branch_id=branch_id,
        initial_focal_entity_id=focal_id,
    )
