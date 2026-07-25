from __future__ import annotations

from uuid import uuid4

from story_engine.persistence.tenant_context import set_tenant_context


class Cursor:
    def __init__(self) -> None:
        self.statement: str | None = None
        self.params: tuple[str] | None = None

    def __enter__(self) -> Cursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, statement: str, params: tuple[str]) -> None:
        self.statement = statement
        self.params = params


class ConnectionStub:
    def __init__(self) -> None:
        self.cursor_value = Cursor()

    def cursor(self) -> Cursor:
        return self.cursor_value


def test_tenant_context_uses_bound_transaction_local_setting() -> None:
    connection = ConnectionStub()
    user_id = uuid4()

    set_tenant_context(connection, user_id)  # type: ignore[arg-type]

    assert connection.cursor_value.statement == "SELECT set_config('app.user_id', %s, true)"
    assert connection.cursor_value.params == (str(user_id),)
