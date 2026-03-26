# Launch Readiness

## Production posture

- Account-based workspace access using signed session cookies, CSRF protection, and login lockouts.
- Persistent project, site, and analysis storage backed by SQLite or Postgres.
- Bulk CSV intake and export workflows for analyst teams that still work in spreadsheets.
- Admin-managed analysts, viewers, and additional admins from inside the app.
- Audit trail for auth events, user changes, project changes, site changes, and analysis runs.
- Response security headers, trusted host support, gzip compression, and request IDs.
- Alembic migrations for repeatable schema rollout.

## Environment checklist

- Set `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` before exposing the app to users.
- Set `SESSION_SECRET` to a long random value in any shared environment.
- Keep `APP_ACCESS_PASSWORD` empty unless you are migrating from the older pilot password model.
- Use managed Postgres in production through `DATABASE_URL`.
- Keep `AUTO_CREATE_SCHEMA=false` in production so schema changes only happen via migrations.
- Keep `RUN_DB_MIGRATIONS=true` in the container start command for Render deploys.

## Pre-launch verification

- Run `pytest --cov=app --cov-report=term-missing --cov-fail-under=95`.
- Run `alembic upgrade head` against a clean database.
- Confirm `/health` returns `200`.
- Confirm `/ready` returns `200` after migrations complete.
- Confirm admin login, user creation, CSV import, project export, rankings export, memo export, and activity feed visibility in the live app.

## Operating model

- Start with one bootstrap admin account, then create named accounts for analysts and viewers from the in-app admin panel.
- Review imported CSVs before running analysis to avoid garbage-in reports.
- Treat the tool as a screening and triage product, not final engineering signoff.
- Rotate bootstrap credentials after first login and use user-level password resets from the admin panel when team membership changes.
