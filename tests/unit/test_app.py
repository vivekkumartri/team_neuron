from __future__ import annotations

from typing import Any

from story_engine.app import create_app


def test_health_endpoint_does_not_expose_connection_values(monkeypatch: Any) -> None:
    monkeypatch.setenv("PGHOST", "internal-db-host")  # type: ignore[attr-defined]
    monkeypatch.setenv("PGDATABASE", "story-engine")  # type: ignore[attr-defined]
    monkeypatch.setenv("PGUSER", "runtime-identity")  # type: ignore[attr-defined]
    monkeypatch.setenv("ENDPOINT_NAME", "projects/example/branches/dev/endpoints/primary")  # type: ignore[attr-defined]

    route = next(
        route for route in create_app().routes if getattr(route, "path", None) == "/api/v1/health"
    )
    response = route.endpoint()  # type: ignore[union-attr]

    assert response.status_code == 200
    assert response.body == (
        b'{"status":"ok","environment":"development","lakebase_resource_bound":true}'
    )


def test_readiness_requires_a_successful_database_query(monkeypatch: Any) -> None:
    monkeypatch.setenv("PGHOST", "internal-db-host")  # type: ignore[attr-defined]
    monkeypatch.setenv("PGDATABASE", "story-engine")  # type: ignore[attr-defined]
    monkeypatch.setenv("PGUSER", "runtime-identity")  # type: ignore[attr-defined]
    monkeypatch.setenv("ENDPOINT_NAME", "projects/example/branches/dev/endpoints/primary")  # type: ignore[attr-defined]
    monkeypatch.setattr("story_engine.app.lakebase_is_ready", lambda _settings: False)

    route = next(
        route
        for route in create_app().routes
        if getattr(route, "path", None) == "/api/v1/readiness"
    )
    response = route.endpoint()  # type: ignore[union-attr]

    assert response.status_code == 503
    assert response.body == b'{"status":"unavailable"}'
