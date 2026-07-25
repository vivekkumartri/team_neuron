"""OAuth-authenticated Lakebase connection primitives.

The Databricks App supplies non-secret PostgreSQL metadata through PG* variables.
Each physical connection receives a newly minted short-lived OAuth database token;
tokens are intentionally never persisted or returned by an API.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from databricks.sdk import WorkspaceClient
from psycopg import Connection, connect

from story_engine.api.settings import RuntimeSettings

logger = logging.getLogger(__name__)


@contextmanager
def lakebase_connection(settings: RuntimeSettings) -> Iterator[Connection[object]]:
    """Open one OAuth-authenticated Lakebase connection without persisting tokens."""

    if not settings.database_resource_bound:
        raise RuntimeError("Lakebase resource is not bound")
    credential = WorkspaceClient().postgres.generate_database_credential(
        endpoint=settings.database_endpoint or ""
    )
    with connect(
        dbname=settings.database_name,
        user=settings.database_user,
        host=settings.database_host,
        port="5432",
        sslmode="require",
        password=credential.token,
        connect_timeout=5,
    ) as connection:
        yield connection


def lakebase_is_ready(settings: RuntimeSettings) -> bool:
    """Return whether the bound Lakebase resource accepts an authenticated query."""

    if not settings.database_resource_bound:
        return False

    try:
        with lakebase_connection(settings) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except Exception as error:
        # A readiness endpoint must fail closed without exposing provider, OAuth,
        # or database detail to callers. Operational diagnostics remain in App logs.
        logger.warning("Lakebase readiness probe failed: %s", type(error).__name__)
        return False
