TASK 31–32 browser E2E
=====================

These tests use Chromium, the real Next.js UI and FastAPI handlers, and the
existing `TEST_DATABASE_URL` PostgreSQL migration/savepoint fixtures. Every test
gets a synthetic catalog and isolated database state. Sample intervals belong
only to these fixtures; no CSV or YouTube API key is required.

Setup (from `backend`): `pip install -e ".[dev]"`, then
`python -m playwright install chromium`. Install frontend dependencies with
`npm ci` in `frontend`. Set `TEST_DATABASE_URL` to a disposable PostgreSQL database.
The existing database fixture skips when that variable is absent. The E2E
directory skips when the optional Playwright package is absent.

Run from `backend`: `python -m pytest tests/e2e`.
The harness starts and stops Next dev on a free loopback port; do not run another
Next dev process against this same frontend directory at the same time. Startup
logs are retained in pytest's temporary directory. No backend server is needed:
browser API requests are passed to TestClient, preserving browser Cookie and
backend Set-Cookie headers. TestClient's own cookie jar is cleared before every
request so it cannot conceal a session persistence regression.

YouTube iframe documents and the IFrame API script are fulfilled locally. All
other external browser requests fail the test, and backend HTTPX network
transports are blocked. Playback coverage verifies the Play interaction and
player mounting; it does not test real YouTube playback. Application/API responses,
scoring, route guards, and persistence are not mocked.

The onboarding matrix covers six samples, the two-sample extension, all voice
modes, selected language/no language preference, extra selections/Skip, reload
resume, first My Taste, and Home. Retention covers feedback evidence, item-only
Skip, persisted saving/removal, Search without learning, and Discover attribution
versus Home, Search, and Saved likes.

Route consistency: UI_FLOW.md, frontend, and backend use
`/onboarding/languages`.
