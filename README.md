# ASMR Recommender

Next.js, TypeScript, and Tailwind frontend with a FastAPI backend.
Includes PostgreSQL schema/migrations, taxonomy seed, and anonymous session resume API.

## Requirements

- Node.js 20.9+ and npm (Node.js 24 LTS suggested)
- Python 3.11+
- PostgreSQL (validated with PostgreSQL 17)

Run the following commands from the repository root in two terminals.
Commands below use PowerShell.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --reload --env-file .env --port 8000
```

API health: http://localhost:8000/health returns `{"status":"ok"}`.
Interactive API docs: http://localhost:8000/docs.
`CORS_ORIGINS` is a comma-separated list of allowed frontend origins.

### Anonymous session

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
and set `SESSION_SECRET` in `backend/.env`. Keep it private and stable across restarts
and backend workers; changing it invalidates existing session cookies. Session requests
fail configuration validation if the secret is shorter than 32 bytes.
`SESSION_COOKIE_SECURE` defaults to `true`; the example sets it to `false` for local
HTTP development. Use `true` with HTTPS in production.

`POST /api/v1/session` creates or resumes an anonymous user using a signed, HttpOnly,
SameSite=Lax cookie with a rolling one-year lifetime. Invalid or deleted-user cookies
start a fresh profile. Identity is accepted only from the signed cookie, never a
request user ID. Browser requests must use `credentials: "include"`; configure the
frontend's exact origin in `CORS_ORIGINS` and deploy frontend/API on the same site.

The response contains `initial_test_completed`, `onboarding_completed`, and
`next_route`: `/test`, `/onboarding/voice`, `/onboarding/languages`, or
`/onboarding/extra-preferences` for the first incomplete step. No Talking bypasses
language; specific saved languages or No preference complete the language step.
Completed returning users always receive `/home`. Step submission endpoints and the
first-completion My Taste redirect belong to later tasks.

## Database

Create a local PostgreSQL role and database using your PostgreSQL administrator
account (the following commands prompt for passwords):

```powershell
createuser -U postgres --pwprompt asmr
createdb -U postgres --owner=asmr asmr
createdb -U postgres --owner=asmr asmr_test
```

Set `DATABASE_URL` in `backend/.env` using the example, replacing `change_me`
with your local password (URL-encode reserved characters). From `backend/`, run:

```powershell
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic current
```

Alembic and the application load `backend/.env`; existing environment variables
take precedence. Migrations create all 13 MVP tables and nine query indexes.
No tables are created automatically at application startup, and `/health` remains
a liveness endpoint independent of the database. Application code can use
`app.database.get_session` as a FastAPI dependency and explicitly commit writes.

For a disposable database only, `python -m alembic downgrade base` removes the
schema tables and their data. Use `python -m alembic revision --autogenerate -m
"description"` for future changes and review generated migrations before applying.

The database enforces keys, required values, declared value sets, sample bounds,
and preference score bounds. Cross-table state changes (including clearing language
preferences), manual tag precedence, and evidence updates belong to later application
tasks. Foreign keys preserve history with PostgreSQL's default NO ACTION behavior.
Required foreign keys and boolean flags are non-null; unspecified timestamps must
be supplied by callers. Only `videos.created_at` has a database `now()` default.

## Taxonomy seed

After applying migrations, run from `backend/`:

```powershell
.\.venv\Scripts\python -m app.seed_taxonomy
```

This loads `DATABASE_URL` using the same configuration as Alembic and inserts the
27 canonical v2.0 keys: 10 Sound, 3 Voice, 4 Visual, 4 Format, 3 Speed, and 3 Intensity.
All 10 Sound keys are core; all new rows are active. Sound descriptions use the
spec's examples; other descriptions remain null. Speed/Intensity display names
use title-cased keys because the spec does not provide separate display labels.
Languages, onboarding voice modes, aliases, and future subtypes are not seeded.

The command is transactional and safe to repeat. It inserts missing keys without
replacing IDs, existing display text/descriptions, or active flags, and leaves other
rows untouched. A conflicting family or core flag fails with a nonzero exit code
and rolls back new rows; semantic changes require an explicit version/migration plan.
It reports the number inserted (27 on an empty table, 0 on a repeat run).
There is no schema change or automatic seed at application startup.

## Frontend

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open http://localhost:3000. The bootstrap page calls the backend `/health`
from the browser and displays “Backend is healthy.” on success, or an
unavailable message on failure. Frontend health is at http://localhost:3000/health.
`NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000`; restart the dev
server after changing it. Public frontend variables must never contain secrets.

## Checks

From `backend/`:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```

Set `TEST_DATABASE_URL` in `backend/.env` to your `asmr_test` database to enable
PostgreSQL migration and seed tests. They use a unique schema in a rolled-back
transaction, cover migrations, constraints, seed idempotency and conflicts, and
never modify `public`.
Without this variable, PostgreSQL tests are explicitly skipped; offline migration
and health tests still run. Tests do not call YouTube.

From `frontend/`:

```powershell
npm run lint
npm run build
```

Use `npm start` to serve the production frontend after building.
On macOS/Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python`
and `cp` in place of `Copy-Item`.
Local env files, virtual environments, and generated build files are ignored by Git.
