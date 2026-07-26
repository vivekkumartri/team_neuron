# Repository Guidelines

## Project Structure & Module Organization

The backend is a Python 3.11 FastAPI application under `src/story_engine/`, organized into `api`, `domain`, `agents`, `persistence`, `security`, and `workers`. Frontend code lives in `web/` as a Next.js/TypeScript app; shared client utilities are in `web/lib/` and UI is in `web/components/`. Tests are grouped by purpose in `tests/unit`, `tests/integration`, `tests/contract`, `tests/security`, `tests/performance`, and `tests/e2e`. SQL migrations are in `migrations/`; deployment definitions are in `resources/` and `databricks.yml`; operational helpers are in `scripts/`.

## Build, Test, and Development Commands

Install dependencies with `python -m pip install -e '.[dev]'` and `npm ci`.

- `pytest -q` runs the Python suite; database-backed tests are skipped unless `TEST_DATABASE_URL` is configured.
- `ruff check .` and `mypy src/story_engine` run linting and strict type checking.
- `npm run typecheck` checks the frontend; `npm run test` runs Node tests.
- `npm run build` creates the static Next.js export in `web/out`; `npm run dev` starts the frontend dev server.
- For a full local stack, use `docker compose up -d`, run `python3 scripts/migrate.py`, then start `uvicorn story_engine.app:app --reload --port 8000` with the local environment variables described in `LOCAL_DEV.md`.
- After installing Chromium, `npx playwright test` runs browser tests in `tests/e2e`.

## Coding Style & Naming Conventions

Use four-space indentation in Python, a 100-character Ruff line limit, explicit type annotations, and imports formatted by Ruff. Keep mypy strict-clean. Use TypeScript types rather than `any`; name React components in PascalCase, hooks with `use...`, and files consistently with their exported component. Python tests use `test_*.py`; Playwright tests use `*.spec.ts`.

## Testing Guidelines

Add focused unit or contract coverage with behavior changes, and add security or integration coverage for tenant isolation, persistence, authentication, or policy changes. There is no configured coverage threshold, but all CI checks must pass.

## Commit & Pull Request Guidelines

Recent commits use short, imperative, conventional-style prefixes such as `feat(api):`, `fix:`, `test:`, and `chore(platform):`. Keep commits focused. Pull requests should explain the behavior change, list validation commands, link the relevant issue or task, call out migrations/configuration changes, and include UI screenshots or recordings when frontend behavior changes. Never commit secrets; local `.env` files are ignored.
