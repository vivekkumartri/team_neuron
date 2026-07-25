from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID

import pytest
from psycopg.types.json import Jsonb

from story_engine.api.auth import AuthenticatedUser
from story_engine.api.routes import preferences


class _Cursor:
    def __init__(self, result: tuple[object, ...]) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._result = result

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[object, ...]) -> None:
        self.calls.append((statement, parameters))

    def fetchone(self) -> tuple[object, ...]:
        return self._result


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self) -> _Cursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True


@pytest.mark.parametrize("value", [True, "reader-first", 3, {"contrast": "high"}])
def test_upsert_preference_adapts_all_values_as_jsonb(
    monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    cursor = _Cursor((user_id, "accessibility", value, "EXPLICIT", "2026-01-01", None))
    connection = _Connection(cursor)

    @contextmanager
    def fake_tenant_connection(_: AuthenticatedUser):
        yield connection

    monkeypatch.setattr(preferences, "tenant_connection", fake_tenant_connection)
    user = AuthenticatedUser(id=user_id, databricks_user_id="user-1", email="test@example.com")

    preferences.upsert_preference(
        preferences.PreferenceInput(preference_key="accessibility", preference_value=value), user
    )

    assert connection.committed
    bound_value = cursor.calls[0][1][2]
    assert isinstance(bound_value, Jsonb)
    assert bound_value.obj == value
