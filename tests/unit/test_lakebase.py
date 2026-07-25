from __future__ import annotations

from story_engine.api.settings import RuntimeSettings
from story_engine.persistence.lakebase import lakebase_is_ready


def test_lakebase_readiness_fails_closed_when_oauth_or_database_is_unavailable() -> None:
    settings = RuntimeSettings(
        database_host="host",
        database_name="database",
        database_user="user",
        database_endpoint="projects/example/branches/dev/endpoints/primary",
    )

    assert lakebase_is_ready(settings) is False
