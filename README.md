# Brahma

Brahma is a multi-tenant, agent-assisted branching-story application.

## Specifications

- `requirements.md` — product requirements
- `design.md` — technical and UI specification
- `task.md` — implementation tracker
- `requirements-reconciliation.md` — authoritative resolution of legacy-source conflicts

## Local development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
npm install
pytest
ruff check .
mypy src/story_engine
npm run typecheck
```

Databricks resources are deployed through Declarative Automation Bundles after workspace credentials and target variables are configured.

