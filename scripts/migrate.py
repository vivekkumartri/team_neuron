"""Idempotent SQL migration runner for Lakebase Postgres."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import psycopg

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[1] / "migrations"


class MigrationDriftError(RuntimeError):
    """An applied migration was changed after it reached a database."""


def migration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_migrations(connection: psycopg.Connection[object]) -> list[str]:
    """Apply ordered migrations once and reject checksum drift."""

    applied_versions: list[str] = []
    migration_files = sorted(MIGRATIONS_DIRECTORY.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, checksum TEXT NOT NULL, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        for path in migration_files:
            version = path.name.split("_", maxsplit=1)[0]
            checksum = migration_checksum(path)
            cursor.execute("SELECT checksum FROM schema_migrations WHERE version = %s", (version,))
            existing = cursor.fetchone()
            if existing:
                if existing[0] != checksum:
                    raise MigrationDriftError(f"Migration checksum drift: {path.name}")
                continue
            cursor.execute(path.read_text(encoding="utf-8"))
            cursor.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                (version, checksum),
            )
            applied_versions.append(version)
    connection.commit()
    return applied_versions


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be supplied by the migration environment")
    with psycopg.connect(database_url) as connection:
        applied = apply_migrations(connection)
    print(f"Applied migrations: {', '.join(applied) or 'none'}")


if __name__ == "__main__":
    main()
