# ASMR Recommender

Next.js/TypeScript frontend, FastAPI backend, and PostgreSQL. Commands below use
PowerShell from the repository root unless a working directory is specified.

## Local setup

Install Python 3.11+, Node.js 24 LTS with npm, and PostgreSQL 17. Create databases
using your PostgreSQL administrator account (passwords are prompted):

```powershell
createuser -U postgres --pwprompt asmr
createdb -U postgres --owner=asmr asmr
createdb -U postgres --owner=asmr asmr_test
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Edit `backend/.env`: set `SESSION_SECRET` to the generated value and replace the
`DATABASE_URL` password with your database password (URL-encode reserved characters).
Set `TEST_DATABASE_URL` to the separate `asmr_test` database for validation.
Before serving requests, from `backend/` with the virtual environment active:

```powershell
python -c "from app.sessions import session_settings; session_settings()"
python -m alembic upgrade head
python -m app.seed_taxonomy
python -m uvicorn app.main:app --reload --env-file .env --port 8000
```

In another terminal, from the repository root:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open http://localhost:3000. `/` resumes the anonymous session and routes fresh users
to `/test`, incomplete users to their next step, and completed users to `/home`.
The conditional language route is `/onboarding/languages`.
On macOS/Linux use `source .venv/bin/activate` and `cp` instead.

## Docker setup

Install Docker with Compose v2 and Linux container support. From the root:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Generate two independent values and put them in root `.env` as `POSTGRES_PASSWORD`
and `SESSION_SECRET`. Without Python, use a password manager to generate random
URL-safe values of at least 32 characters. Root `.env` is Compose configuration;
`backend/.env` and `frontend/.env.local` are for the non-Docker setup.

```powershell
docker compose up --build -d
docker compose ps
docker compose logs backend
docker compose down
```

Startup waits for PostgreSQL, validates the session configuration, migrates to
Alembic head, and runs the idempotent taxonomy seed before FastAPI serves requests.
Frontend startup waits for backend health. A failed migration/seed stops backend
startup. This local setup uses one backend instance; coordinate migrations as a
separate release step before scaling in production.

PostgreSQL data persists in `postgres_data` across `docker compose down`. Do not
use `down -v` unless deliberately deleting the database. Changing the root password
does not change the password of an already initialized PostgreSQL volume.
Database ports are not published; app ports bind to host loopback only.

The browser calls `NEXT_PUBLIC_API_BASE_URL`, so the local value is
`http://localhost:8000`, not the container hostname `backend`. Next.js embeds this
public value at build time: rebuild the frontend after changing it. Keep browser
hostnames consistent (do not mix localhost and 127.0.0.1 for session flows).
No secret is passed as a build argument. Docker contexts exclude local env files.

Manual migration/seed commands, if needed:

```powershell
docker compose exec backend python -m alembic upgrade head
docker compose exec backend python -m app.seed_taxonomy
```

## Environment and health

| Variable | Required / purpose |
| --- | --- |
| `DATABASE_URL` | Backend PostgreSQL URL; Compose derives it using the internal `db` host. |
| `SESSION_SECRET` | Random secret of at least 32 bytes; stable across workers/restarts. |
| `SESSION_COOKIE_SECURE` | Defaults to `true` in code; local HTTP examples explicitly use `false`. |
| `CORS_ORIGINS` | Comma-separated exact frontend origins, without paths, trailing slashes, or wildcards. Local default: `http://localhost:3000`. |
| `NEXT_PUBLIC_API_BASE_URL` | Public browser-reachable API origin; frontend build-time setting. |
| `POSTGRES_PASSWORD` | Required for Compose; use a URL-safe random value. |
| `YOUTUBE_API_KEY` | Server-only; required for catalog collection/refresh, not offline tests. |
| `YOUTUBE_TIMEOUT_SECONDS` | Optional, default 10; greater than 0 and at most 120. |
| `YOUTUBE_MAX_RETRIES` | Optional, default 2; range 0–5. |
| `TEST_DATABASE_URL` | Separate disposable PostgreSQL database for integration/E2E tests. |

Backend and Alembic load `backend/.env`; existing environment variables take
precedence. Never commit local env files or put secrets in `NEXT_PUBLIC_*`.

- Backend: http://localhost:8000/health returns `{"status":"ok"}`.
- Frontend: http://localhost:3000/health returns `{"status":"ok"}`.
- API documentation: http://localhost:8000/docs.

Health endpoints are liveness checks, not database/catalog/YouTube readiness checks.
Taxonomy seed inserts 27 canonical keys on an empty database and 0 on a repeat run;
it preserves existing IDs and values, and rejects conflicting key semantics.

## Catalog and reviewed samples

Migration and taxonomy seed do not populate videos or listening samples. From
`backend/` with a server-side API key configured:

```powershell
python -m app.scripts.collect_youtube
python -m app.scripts.import_trigger_samples reviewed.csv
python -m app.scripts.refresh_youtube --stale-days 1
```

Use the importer with an independently reviewed sample CSV. Six base Sound samples
and at least two eligible optional samples are needed for the full onboarding demo.
Never invent timestamps or import E2E fixture intervals into the real catalog.
For automatic metadata tagging, run `python -m app.scripts.tag_videos` with
`DATABASE_URL` exported in the process environment (this CLI does not load `.env`).
Compose already provides that environment variable.
For Docker, prefix module commands with `docker compose exec backend`; to import a
reviewed file first copy it with `docker compose cp reviewed.csv backend:/tmp/reviewed.csv`
and pass `/tmp/reviewed.csv` to the importer.

The pipeline requests metadata through YouTube Data API v3 only. Playback uses
visible official YouTube embeds/IFrame API, with controls enabled. There is no
video/audio downloading, extraction, or rehosting path in the inspected code.
Refresh marks missing/private videos unavailable and non-embeddable videos blocked;
active catalog queries exclude those statuses. Failed API batches do not infer
that videos are missing. The player offers recovery when playback fails.

Schedule refresh externally (for example daily with `--stale-days 1`), monitor its
exit status and quota, and investigate failures before metadata reaches 30 days.
There is no bundled scheduler or read-time stale-metadata cutoff: overdue rows can
remain visible if refresh stops. Operators must restore refresh or remove affected
catalog entries from active service; this is a production operational requirement.

## Production configuration

Use HTTPS and explicitly set `SESSION_COOKIE_SECURE=true`; local Compose defaults
are for HTTP development. Serve frontend and API on the same site for SameSite=Lax
cookies, with exact HTTPS frontend origins in `CORS_ORIGINS`. Credentialed CORS is
enabled, and browser API calls include credentials. Wildcard origins are rejected.

Identity comes only from the signed HttpOnly cookie; request user IDs do not select
another user's profile. Keep `SESSION_SECRET` random, private, and identical across
workers. Rotation invalidates existing cookies. No OAuth/authentication is added.

Use a deployment secret store or protected runtime environment for database,
session, and YouTube credentials. Restrict the server-side YouTube key to the Data
API and appropriate server restrictions. Do not enable debug tracebacks, SQL echo,
or HTTP wire/header logging in production. FastAPI defaults to generic unhandled
500 responses; YouTube errors expose fixed categories rather than response bodies
or credentials, and the application SQL engine hides SQL parameter values in errors.
Restrict access to server logs and redact credentials in deployment log collectors.
Back up PostgreSQL and arrange migrations, refresh scheduling, TLS, and monitoring
before deployment. This repository does not establish a production deployment.

## Final release validation checklist

All items below are pending until actually executed and recorded. No tests, lint,
builds, Docker builds, or deployment verification were run for this hardening block.

- [ ] Install backend dependencies with `python -m pip install -e ".[dev]"` from
  `backend/` in the active virtual environment; install frontend dependencies with
  `npm ci` from `frontend/`.
- [ ] Set `TEST_DATABASE_URL` to a disposable PostgreSQL database. Without it,
  database-dependent integration/E2E cases skip; a skipped run is not full validation.
- [ ] From `backend/`: `python -m playwright install chromium`. Browser binaries are
  installed separately, never at Python package installation time. On Linux runners
  that need OS libraries, use `python -m playwright install --with-deps chromium`.
- [ ] From `backend/`: `python -m pytest` and `python -m ruff check .`.
- [ ] From `frontend/`: `npm run lint` and `npm run build`. Use `npm start` after a
  successful build for the production frontend smoke test.
- [ ] From `backend/`: `python -m pytest tests/e2e`. The harness starts Next dev and
  uses real API/database behavior with locally stubbed YouTube; stop any other Next
  dev process for this checkout first. See `backend/tests/e2e/README.md`.
- [ ] Create a separate empty database, point `DATABASE_URL` at it, then from
  `backend/` run `python -m alembic upgrade head`, `python -m alembic current`, and
  `python -m app.seed_taxonomy` twice. Confirm head and seed counts 27 then 0.
  Restore the normal `DATABASE_URL` afterward; do not reset an existing database.
- [ ] Run `docker compose up --build -d` with a fresh project/volume and confirm all
  three services become healthy, migrations complete, and taxonomy is seeded.
- [ ] Verify both `/health` endpoints, then verify an API session request succeeds.
- [ ] With reviewed samples/catalog loaded, use a fresh browser profile: six Sound
  samples, optional two, voice choice, conditional languages, checkbox extras,
  first My Taste, then Home. Check No Talking bypasses languages and reload resumes.
- [ ] Return with the same browser cookie: land on Home, verify saved items/taste
  persist, Like/Dislike work, Skip affects only the item, and Search filters alone
  do not change taste. Verify Discover, Search, Saved, and My Taste navigation.
- [ ] Verify real YouTube playback and an unavailable-video recovery manually;
  offline E2E tests do not validate live YouTube or production networking.

## Known MVP limitations

Identity is an anonymous browser cookie, with no cross-device profile sync or
account recovery after cookie loss. Recommendations are deterministic content-based
only. Onboarding requires manually reviewed timestamps. Catalog collection and
freshness depend on YouTube Data API availability/quota and an external refresh
schedule. An empty setup can pass liveness checks while onboarding lacks samples.
Production rollout remains pending the checklist and operational setup above.
