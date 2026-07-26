# Running Brahma locally (Docker Postgres, no Databricks)

This is a local-only path for development before deploying to Databricks.
It reuses the exact same code as production — no separate "local app" — via
three narrow, explicitly-gated escape hatches that are structurally
unreachable when actually deployed to Databricks:

- `LOCAL_DATABASE_URL` — bypasses Lakebase OAuth and connects straight to
  the docker-compose Postgres (`persistence/lakebase.py`). `databricks.yml`
  never sets this, so the deployed App never takes this path.
- `STORY_ENGINE_LOCAL_DEV=1` — makes `api/auth.py` accept requests without
  the Databricks Apps reverse-proxy identity headers (fixed dev user), and
  makes `services/databricks_jobs.py` run the generation worker in-process
  in a background thread instead of calling the Databricks Jobs API
  (`LocalJobLauncher`, since there is no Databricks Jobs API to call
  locally).

## 1. Start Postgres

```
docker compose up -d
```

This starts Postgres 16 on `localhost:5432` (db/user/password: `story_engine`
/ `story_engine` / `story_engine_dev`), with a persistent volume so data
survives restarts. `docker compose down -v` wipes it.

## 2. Apply migrations

```
export LOCAL_DATABASE_URL="postgresql://story_engine:story_engine_dev@localhost:5432/story_engine"
export DATABASE_URL="$LOCAL_DATABASE_URL"   # scripts/migrate.py reads this name
python3 scripts/migrate.py
```

## 3. Run the backend

```
export LOCAL_DATABASE_URL="postgresql://story_engine:story_engine_dev@localhost:5432/story_engine"
export STORY_ENGINE_LOCAL_DEV=1
export OPENAI_API_KEY=sk-...        # required for any real generation/voice call
python3 -m pip install -e ".[dev]" --break-system-packages   # first time only
uvicorn story_engine.app:app --reload --port 8000
```

Health check: `curl http://localhost:8000/api/v1/health` should report
`"lakebase_resource_bound": true`.

## 4. Build and serve the frontend

The app serves the frontend as a static export from `web/out` (identical to
how the Databricks App serves it) rather than running a separate Next.js
dev server, since `next.config.ts` uses `output: "export"` (no rewrites/proxy
support in that mode).

```
cd web
npm install     # first time only
npm run build   # writes web/out
```

Restart (or just refresh — StaticFiles serves from disk) the backend after
rebuilding the frontend; then open `http://localhost:8000`.

If you'd rather iterate on the frontend with hot reload, run `npm run dev`
in `web/` on its own port (default 3000) instead of building/serving the
static export. Create `web/.env.local`:

```
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
```

This is what fixes the `PATCH .../api/v1/me/preferences 404` you get from
`npm run dev` out of the box — that 404 comes from the Next.js dev server
itself (no `/api/v1` route exists there), not from the FastAPI backend. With
`NEXT_PUBLIC_API_BASE` set, requests go straight to the backend on 8000
instead. The backend's CORS middleware (enabled automatically whenever
`STORY_ENGINE_LOCAL_DEV=1`, see `app.py`) allows `localhost:3000` — no other
origin, and only when that env var is set — so this never opens anything up
in the deployed App.

## Known local-only gaps

- **Chapter narration/TTS and voice transcription** call OpenAI directly —
  they work locally exactly as in production as long as `OPENAI_API_KEY` is
  set. No Databricks secret scope is needed locally (`_load_openai_api_key`
  in `workers/generation_job.py` prefers `settings.openai_api_key` — i.e.
  the plain env var — before ever touching a Databricks secret).
- **`report_job`, `memory_compaction_job`, `audit_export_job`** are still
  Databricks-Jobs-only entry points; only `generation_job` has a local
  in-process launcher (`LocalJobLauncher`) today, since that's the one on
  the interactive request path. These three aren't wired to run locally yet.
- **Unity Catalog / Delta audit sink** doesn't exist locally — audit export
  will simply have nothing to talk to. Fine for local iteration.

## Migrating to Databricks later

Nothing about this path touches `databricks.yml`/`resources/*.yml` — when
you're ready to deploy for real, `databricks bundle deploy -t dev` and the
existing Lakebase/OAuth/Databricks-Jobs code paths take over exactly as
before (this local path never sets `LOCAL_DATABASE_URL`/
`STORY_ENGINE_LOCAL_DEV` in that flow, so nothing needs to be "undone").
