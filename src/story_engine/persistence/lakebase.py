"""OAuth-authenticated Lakebase connection primitives.

The Databricks App supplies non-secret PostgreSQL metadata through PG* variables.
Each physical connection receives a newly minted short-lived OAuth database token;
tokens are intentionally never persisted or returned by an API.
"""

from __future__ import annotations

import logging

from databricks.sdk import WorkspaceClient
from psycopg import connect

from story_engine.api.settings import RuntimeSettings

logger = logging.getLogger(__name__)


def lakebase_is_ready(settings: RuntimeSettings) -> bool:
    """Return whether the bound Lakebase resource accepts an authenticated query."""

    if not settings.database_resource_bound:
        return False

    try:
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
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except Exception as error:
        # A readiness endpoint must fail closed without exposing provider, OAuth,
        # or database detail to callers. Operational diagnostics remain in App logs.
        logger.warning("Lakebase readiness probe failed: %s", type(error).__name__)
        return False
