"""One-off diagnostic: list generation_jobs rows currently counted as
'active' by the CONCURRENT_GENERATION_JOBS quota (status QUEUED/RUNNING),
so we can tell a genuinely-in-progress job apart from an orphaned one that
never actually got picked up by a worker.

Usage: DATABASE_URL=... python3 scripts/check_stuck_jobs.py
"""

from __future__ import annotations

import os

import psycopg

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL must be set")

with psycopg.connect(database_url) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, branch_id, status, created_at, updated_at, lease_expires_at, "
            "now() - created_at AS age "
            "FROM generation_jobs "
            "WHERE status IN ('QUEUED', 'RUNNING') "
            "ORDER BY created_at"
        )
        rows = cursor.fetchall()

if not rows:
    print("No jobs currently counted as active (QUEUED/RUNNING). Quota should be free.")
else:
    for row in rows:
        job_id, branch_id, status, created_at, updated_at, lease_expires_at, age = row
        print(
            f"job_id={job_id} branch_id={branch_id} status={status} "
            f"created_at={created_at} updated_at={updated_at} "
            f"lease_expires_at={lease_expires_at} age={age}"
        )
