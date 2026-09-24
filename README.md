# ASMR Recommender

TASK 01 bootstrap: Next.js, TypeScript, and Tailwind frontend with a FastAPI backend.
No database or product flows are implemented yet.

## Requirements

- Node.js 20.9+ and npm (Node.js 24 LTS suggested)
- Python 3.11+

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

From `frontend/`:

```powershell
npm run lint
npm run build
```

Use `npm start` to serve the production frontend after building.
On macOS/Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python`
and `cp` in place of `Copy-Item`.
Local env files, virtual environments, and generated build files are ignored by Git.
