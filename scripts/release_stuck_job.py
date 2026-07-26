"""One-off: mark a specific stuck (never-claimed) generation_jobs row as
FAILED so it stops counting against CONCURRENT_GENERATION_JOBS quota.

Usage: DATABASE_URL=... python3 scripts/release_stuck_job.py <job_id>
"""

from __future__ import annotations

import os
import sys

import psycopg

if len(sys.argv) != 2:
    raise SystemExit("Usage: python3 scripts/release_stuck_job.py <job_id>")

job_id = sys.argv[1]
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL must be set")

with psycopg.connect(database_url) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE generation_jobs SET status = 'FAILED', updated_at = now() "
            "WHERE id = %s AND status IN ('QUEUED', 'RUNNING') "
            "RETURNING id, status",
            (job_id,),
        )
        row = cursor.fetchone()
    connection.commit()

print(f"Updated: {row}" if row else "No matching QUEUED/RUNNING job found (already released?).")
