# Grid Interconnection & Energy Siting Copilot

Grid Interconnection & Energy Siting Copilot is a production-ready pilot for screening renewable energy project sites before teams spend money on deeper diligence. It scores sites against interconnection, permitting, community, and execution heuristics, ranks a portfolio, and generates an investment-style readiness memo.

## What it does

- Scores candidate sites across five major ISO regions.
- Stores persistent projects, sites, and analysis runs.
- Protects the workspace with a shared pilot password and signed session cookies.
- Imports candidate sites from CSV for spreadsheet-based analyst teams.
- Exports project snapshots, ranked analysis CSVs, and memo markdown for investment reviews.
- Ships with automated unit, integration, and migration checks.

## Product scope

This product is designed for early-stage screening, not final engineering signoff. It helps development and investment teams decide where to spend deeper diligence effort faster and more consistently.

## Stack

- FastAPI
- SQLAlchemy
- Alembic
- Pydantic and pydantic-settings
- Jinja2
- Vanilla JavaScript and CSS dashboard
- pytest with coverage gates
- Docker and Render deployment config

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Test

```bash
.venv\Scripts\python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=95
```

## Core API

- `GET /health`
- `GET /ready`
- `GET /api/session`
- `POST /api/session/login`
- `GET /api/reference/regions`
- `GET /api/reference/site-template.csv`
- `POST /api/projects`
- `POST /api/projects/{project_id}/sites/import-csv`
- `POST /api/projects/{project_id}/analysis`
- `GET /api/projects/{project_id}/export`
- `GET /api/projects/{project_id}/analysis/latest.csv`
- `GET /api/projects/{project_id}/analysis/latest.md`

## Production notes

- Use `DATABASE_URL` for Postgres in shared environments.
- Set `APP_ACCESS_PASSWORD` and `SESSION_SECRET` before giving users access.
- Keep `AUTO_CREATE_SCHEMA=false` in production and let Alembic own schema changes.
- Render deployment uses `start.sh`, which runs `alembic upgrade head` before starting Uvicorn.
- See [docs/launch-readiness.md](/Users/ring_/OneDrive/Documents/Playground/grid-interconnection-copilot/docs/launch-readiness.md) for the launch checklist.

## Branch workflow used in this repo

- `codex/mvp-grid-interconnection`
- `codex/feature-site-scoring-api`
- `codex/feature-comparison-and-memos`
- `codex/feature-web-dashboard`
- `codex/feature-deployment-and-ci`
- `codex/feature-project-persistence`
- `codex/feature-user-workspace`
- `codex/feature-security-and-ops`
- `codex/feature-bulk-intake-and-export`
- `codex/feature-migrations-and-launch-readiness`
- `codex/production-hardening`

Each major feature was developed on its own branch and merged into the integration branch before promotion to `main`.
