"""Databricks Apps identity boundary and just-in-time tenant provisioning."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from fastapi import HTTPException, Request, status
from psycopg import Connection

from story_engine.api.settings import load_settings
from story_engine.persistence.lakebase import lakebase_connection
from story_engine.persistence.tenant_context import set_tenant_context


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    databricks_user_id: str
    email: str


def authenticate_request(request: Request) -> AuthenticatedUser:
    """Trust identity headers injected by the Databricks Apps reverse proxy.

    Locally there is no such proxy, so `settings.local_dev_mode` (only ever
    true when a developer explicitly exports `STORY_ENGINE_LOCAL_DEV=1` —
    never set by `databricks.yml`) substitutes one fixed dev identity instead
    of every request 401ing. This never activates in the deployed App.
    """

    settings = load_settings()
    databricks_user_id = request.headers.get("x-forwarded-user")
    email = request.headers.get("x-forwarded-email")
    if not databricks_user_id or not email:
        if settings.local_dev_mode:
            databricks_user_id, email = "local-dev-user", "dev@localhost"
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
            )

    with lakebase_connection(settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT app_provision_user(%s, %s)", (databricks_user_id, email))
            row = cursor.fetchone()
        connection.commit()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Tenant unavailable"
        )
    user_id = cast(tuple[object], row)[0]
    return AuthenticatedUser(
        id=UUID(str(user_id)), databricks_user_id=databricks_user_id, email=email
    )


@contextmanager
def tenant_connection(user: AuthenticatedUser) -> Iterator[Connection[object]]:
    """Return a connection context that applies the current user's RLS scope."""

    with lakebase_connection(load_settings()) as connection:
        set_tenant_context(connection, user.id)
        yield connection
