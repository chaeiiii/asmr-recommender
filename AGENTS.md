# AGENTS.md — ASMR Recommender

## Mission
Implement the MVP exactly from the project specs. Do not redesign product behavior unless a spec is explicitly changed.

## Source of truth
- work order / DoD: `TASKS.md`
- product: `PRODUCT_SPEC.md`
- taxonomy: `TRIGGER_TAXONOMY.md`
- UX: `UI_FLOW.md`
- schema: `DATABASE.md`
- API: `API.md`
- YouTube pipeline: `YOUTUBE_PIPELINE.md`
- recommendation: `RECOMMENDER.md`

Read only the files relevant to the current task to minimize context.

## Stack
Next.js + TypeScript + Tailwind; FastAPI + Python 3.11+; PostgreSQL; SQLAlchemy + Alembic; YouTube Data API v3; YouTube IFrame Player API.

## Hard rules
- Onboarding is cold-start only; completed returning users land on Home.
- Initial test = 6 base Sound samples + optional 2; max 8.
- Voice = talking/no_talking/both; language only for talking/both and is a soft preference.
- Extra-preference step = checkbox only, no playback; unpresented Sound + Visual + Format.
- Unknown/unselected/skip never equals feature dislike.
- Normal-video Skip is item-level de-prioritization only in v1.
- My Taste is a living profile.
- Main nav: Home / Discover / Search / Saved / My Taste.
- Search filters do not update taste by themselves.
- Never download/extract/re-host YouTube media.
- Never invent listening-test timestamps.
- Never hide/cover required YouTube player UI.
- Never commit secrets.
- Taxonomy v2.0 keys are stable.
- No OAuth, social, AI-generation, collaborative filtering, native apps, microservices in MVP.
- DB changes require Alembic migrations.
- Ingestion/import commands must be idempotent.
- Tests must not require live YouTube API calls; mock external calls.

## Validation
Backend: `pytest` and `ruff check .`
Frontend: `npm run lint` and `npm run build`
Run only checks relevant to touched code, plus required integration checks in later tasks.

## Workflow
When asked for `TASK NN`, read that task in `TASKS.md` and only its referenced specs. Implement that task plus strictly necessary prerequisite fixes. Do not start the next task.

## Completion report
Return only:
- files changed;
- implementation summary;
- checks run/results;
- blockers or spec mismatches.
