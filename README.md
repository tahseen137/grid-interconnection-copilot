# Grid Interconnection & Energy Siting Copilot

Grid Interconnection & Energy Siting Copilot is an MVP for screening renewable energy project sites before teams spend money on deeper diligence. It scores sites against interconnection, permitting, community, and execution heuristics, ranks a portfolio, and generates an investment-style readiness memo.

## What it does

- Scores candidate sites across five major ISO regions.
- Compares multiple sites and recommends which one to advance.
- Generates a first-pass interconnection readiness memo.
- Ships with a lightweight dashboard for non-technical users.
- Includes automated tests and CI-ready deployment assets.

## Product scope

This MVP is designed for early-stage screening, not final engineering signoff. It gives development and investment teams a faster way to decide where to spend deeper diligence effort.

## Stack

- FastAPI
- Pydantic
- Jinja2
- vanilla JavaScript + CSS dashboard
- pytest for automated quality control
- Docker + Render config for deployment

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Test

```bash
.venv\Scripts\python -m pytest
```

## API

- `GET /health`
- `GET /api/reference/regions`
- `POST /api/sites/score`
- `POST /api/sites/compare`
- `POST /api/reports/interconnection-memo`

## Branch workflow used in this repo

- `codex/mvp-grid-interconnection`
- `codex/feature-site-scoring-api`
- `codex/feature-comparison-and-memos`
- `codex/feature-web-dashboard`
- `codex/feature-deployment-and-ci`

Each feature was developed on its own feature branch and merged into the integration branch locally.
