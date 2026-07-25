# Runbook: Stuck or Failed Generation Job

## Symptom

A `generation_jobs` row has been `LEASED` past its lease expiry, or a job's
`generation_events` stream stopped advancing (no new `sequence` for several
minutes) while the job is not in a terminal status
(`SUCCEEDED`/`FAILED`/`BLOCKED`/`CANCELLED`).

## Diagnosis

1. Identify the job: `SELECT id, status, leased_at, leased_by, retry_count FROM generation_jobs WHERE id = :job_id;`
2. Check whether the lease has actually expired relative to the configured
   lease duration (`workers/queue.py`'s `claim_next_job` — leases are
   reclaimed via `SELECT ... FOR UPDATE SKIP LOCKED` once expired, so a
   still-live lease is not itself stuck).
3. Check the Databricks Job run history for the corresponding job key
   (`generation_job` in `resources/jobs.yml`) for an actual worker crash vs.
   a merely slow run.

## Recovery

1. If the lease has genuinely expired and no worker is running: `worker/queue.release_job(job_id)` (or the equivalent direct `UPDATE generation_jobs SET status = 'FAILED', leased_at = NULL WHERE id = :job_id AND status = 'LEASED';`) so the job becomes reclaimable.
2. Re-trigger generation from the client (a new `POST` request creates a new
   job row) rather than resubmitting the same stuck row — this repo's
   pattern treats a job as append-only once created.
3. **Never** directly `UPDATE chapters SET status = 'PUBLISHED'` to force a
   result — a stuck job must resolve through the normal candidate →
   evaluator → publish path (`services/generation_pipeline.py`) or be marked
   `FAILED`, so published canon is never a hand-edited artifact.

## Verification

After recovery, the test job's row should show `status = 'FAILED'` and no
`chapters` row was published outside the normal pipeline —
`SELECT * FROM chapters WHERE id = :test_chapter_id AND status = 'PUBLISHED';`
should return nothing for a genuinely stuck test job, or the actual result of
a fresh, successful resubmission.
