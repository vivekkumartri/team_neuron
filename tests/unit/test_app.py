from __future__ import annotations

from typing import Any

from story_engine.app import create_app


def test_health_endpoint_does_not_expose_connection_values(monkeypatch: Any) -> None:
    monkeypatch.setenv("PGHOST", "internal-db-host")  # type: ignore[attr-defined]
    monkeypatch.setenv("PGDATABASE", "story-engine")  # type: ignore[attr-defined]
    monkeypatch.setenv("PGUSER", "runtime-identity")  # type: ignore[attr-defined]

    route = next(route for route in create_app().routes if route.path == "/api/v1/health")
    response = route.endpoint()  # type: ignore[union-attr]

    assert response.status_code == 200
    assert response.body == (
        b'{"status":"ok","environment":"development","lakebase_resource_bound":true}'
    )
