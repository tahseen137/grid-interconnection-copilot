# Launch Readiness

## Production posture

- Password-protected workspace using signed session cookies.
- Persistent project, site, and analysis storage backed by SQLite or Postgres.
- Bulk CSV intake and export workflows for analyst teams that still work in spreadsheets.
- Response security headers, trusted host support, gzip compression, and request IDs.
- Alembic migrations for repeatable schema rollout.

## Environment checklist

- Set `APP_ACCESS_PASSWORD` before exposing the app to users.
- Set `SESSION_SECRET` to a long random value in any shared environment.
- Use managed Postgres in production through `DATABASE_URL`.
- Keep `AUTO_CREATE_SCHEMA=false` in production so schema changes only happen via migrations.
- Keep `RUN_DB_MIGRATIONS=true` in the container start command for Render deploys.

## Pre-launch verification

- Run `pytest --cov=app --cov-report=term-missing --cov-fail-under=95`.
- Run `alembic upgrade head` against a clean database.
- Confirm `/health` returns `200`.
- Confirm `/ready` returns `200` after migrations complete.
- Confirm login, CSV import, project export, rankings export, and memo export in the live app.

## Pilot operating model

- Start with one password-protected workspace for a small analyst team.
- Review imported CSVs before running analysis to avoid garbage-in reports.
- Treat the tool as a screening and triage product, not final engineering signoff.
- Rotate the shared password when pilot membership changes.
