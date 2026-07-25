"""Safe transaction-local tenant context setter."""

from __future__ import annotations

from uuid import UUID

from psycopg import Connection


def set_tenant_context(connection: Connection[object], user_id: UUID) -> None:
    """Set RLS context for the current transaction with a bound parameter."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
