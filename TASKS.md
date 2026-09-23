# Codex Implementation Plan — Ordered Tasks

Use one task per Codex request. Prompt pattern: **`Read AGENTS.md. Implement TASK NN from TASKS.md only.`**

## Phase A — Foundation
### TASK 01 — Repository bootstrap
Create `frontend/` Next.js TypeScript/Tailwind app and `backend/` FastAPI app, env examples, basic README commands, health endpoints.
**DoD:** both dev servers start; frontend can call mocked/backend health endpoint.
**Read:** AGENTS only.

### TASK 02 — PostgreSQL + ORM + migrations
Set up PostgreSQL config, SQLAlchemy, Alembic; implement final schema from DATABASE.md.
**DoD:** fresh migration creates all tables/constraints/indexes.
**Read:** DATABASE.

### TASK 03 — Taxonomy seed
Implement idempotent taxonomy seed for v2.0.
**DoD:** all canonical keys/families inserted exactly once.
**Read:** TRIGGER_TAXONOMY, DATABASE.

### TASK 04 — Anonymous session + route state API
Implement cookie-backed anonymous user session and onboarding next-state logic.
**DoD:** repeat browser session resolves same user; API returns correct next route.
**Read:** PRODUCT_SPEC, API, DATABASE.

## Phase B — YouTube catalog
### TASK 05 — YouTube client
Implement Data API client, config, batching, typed/service wrapper, mocked tests.
**DoD:** search/video metadata methods work against fixtures; no live calls in tests.
**Read:** YOUTUBE_PIPELINE.

### TASK 06 — Catalog collection/upsert
Implement seed-query collection, dedupe, eligibility, videos upsert, run logging.
**DoD:** fixture run is idempotent and rejects invalid/non-embeddable fixtures.
**Read:** YOUTUBE_PIPELINE, DATABASE.

### TASK 07 — Keyword tagger
Implement deterministic taxonomy dictionary, confidences, negation handling, manual override precedence.
**DoD:** fixture videos receive expected multi-label tags.
**Read:** TRIGGER_TAXONOMY, YOUTUBE_PIPELINE.

### TASK 08 — Metadata refresh
Implement stale-video refresh/unavailable handling.
**DoD:** deleted/private/non-embeddable fixtures disappear from active catalog queries.
**Read:** YOUTUBE_PIPELINE, DATABASE.

### TASK 09 — Trigger-sample import tooling
Implement reviewed CSV importer and validation; never invent timestamps.
**DoD:** valid CSV inserts verified sample rows idempotently; invalid ranges fail clearly.
**Read:** PRODUCT_SPEC, YOUTUBE_PIPELINE, DATABASE.

### USER CHECKPOINT A — Real YouTube setup
User supplies `YOUTUBE_API_KEY` locally and may run catalog collection to build the first 300–500-video catalog. Key is never committed.

### USER CHECKPOINT B — Test sample approval
User manually approves about 20–30 representative segments and fills reviewed CSV. Codex imports it; Codex does not choose final timestamps.

## Phase C — Onboarding backend
### TASK 10 — Base test assignment
Stable six-sample assignment covering the six base Sound triggers.
**DoD:** refresh/repeated API call returns same assignment; only verified samples used.
**Read:** PRODUCT_SPEC, API, DATABASE, TRIGGER_TAXONOMY.

### TASK 11 — Test responses + preference evidence
Implement Like/Neutral/Dislike/Skip response idempotency and aggregate preference update.
**DoD:** repeated response does not double-count; Skip creates no feature dislike.
**Read:** API, RECOMMENDER, DATABASE.

### TASK 12 — Optional +2 and test completion
Implement optional extension from remaining four Sound triggers and completion guards.
**DoD:** distinct triggers, stable assignment, max 8 total.
**Read:** PRODUCT_SPEC, API.

### TASK 13 — Voice + conditional language backend
Implement talking/no_talking/both and language rules.
**DoD:** No Talking clears/skips language; no-preference exclusivity enforced.
**Read:** PRODUCT_SPEC, API, RECOMMENDER.

### TASK 14 — Extra checkbox preferences backend
Implement grouped eligible options and weak positive self-report evidence.
**DoD:** already-presented Sound keys excluded; empty Skip completes onboarding.
**Read:** PRODUCT_SPEC, API, RECOMMENDER.

### TASK 15 — My Taste backend
Implement current profile/state derivation, recent discoveries, unknown/low-evidence output.
**DoD:** states are deterministic and are not labeled as probabilities.
**Read:** API, RECOMMENDER, UI_FLOW.

## Phase D — Core product backend
### TASK 16 — content_v1 recommender
Implement candidate filtering, signed weighted score, voice/language soft adjustments, channel diversity, reasons.
**DoD:** deterministic fixture rankings and regression tests pass.
**Read:** RECOMMENDER, DATABASE.

### TASK 17 — Home recommendations API + impressions
Return ranked Home cards and record impressions.
**DoD:** unavailable/non-embeddable/exact-disliked videos excluded.
**Read:** API, RECOMMENDER.

### TASK 18 — Video interactions
Implement play/like/dislike/skip; like/dislike preference updates; exact-video skip cooldown behavior.
**DoD:** skip does not globally penalize video features.
**Read:** API, RECOMMENDER, DATABASE.

### TASK 19 — Saved backend
Implement favorite add/remove/list idempotently.
**DoD:** removing favorite does not create dislike.
**Read:** API, DATABASE.

### TASK 20 — Discover backend
Implement unknown/low-evidence/adjacent exploration and impression logging.
**DoD:** omitted onboarding features remain discoverable; strong dislikes guarded.
**Read:** PRODUCT_SPEC, RECOMMENDER, API.

### TASK 21 — Search backend
Implement catalog filter endpoint for Sound/Voice/Speed/Language/Format/duration and optional text.
**DoD:** combination-filter tests pass; search itself creates no preference evidence.
**Read:** PRODUCT_SPEC, API, TRIGGER_TAXONOMY.

## Phase E — Frontend
### TASK 22 — App shell/session/resume/navigation
Responsive shell, API client, anonymous session bootstrap, onboarding resume guards, post-onboarding bottom nav.
**DoD:** main nav = Home/Discover/Search/Saved/My Taste; completed session starts Home.
**Read:** UI_FLOW, API.

### TASK 23 — Sound-first test UI
Implement 6-base + optional-2 experience with official YouTube embed and response controls.
**DoD:** visible player, progress, Skip, trigger reveal after answer, no UI-hiding hacks.
**Read:** UI_FLOW, PRODUCT_SPEC, API.

### TASK 24 — Voice/language UI
Conditional flow exactly per spec.
**DoD:** No Talking skips language; multi-language/no-preference UX works.
**Read:** UI_FLOW, API.

### TASK 25 — Extra preference UI
Checkbox-only Sound/Visual/Format screen with descriptions and Skip.
**DoD:** no media player; multi-select; only server-eligible items shown.
**Read:** UI_FLOW, API.

### TASK 26 — My Taste UI
Implement first-result and living-profile states.
**DoD:** cards/chips/state labels, unknown section, Discover/Home CTAs; no misleading percentages.
**Read:** UI_FLOW, API.

### TASK 27 — Home UI
Recommendation feed, official player, reasons, feedback/save/skip controls.
**DoD:** interaction state persists and feed handles unavailable video gracefully.
**Read:** UI_FLOW, API.

### TASK 28 — Discover UI
Exploration sections/cards and feedback.
**DoD:** new/adjacent/low-evidence content represented; feedback updates profile after refresh.
**Read:** UI_FLOW, API.

### TASK 29 — Search UI
Mobile filter sheet/chips/results with clear-all.
**DoD:** filters map exactly to backend; searching does not change taste.
**Read:** UI_FLOW, API.

### TASK 30 — Saved UI
Saved list, remove action, empty state.
**DoD:** responsive and linked from bottom nav.
**Read:** UI_FLOW, API.

## Phase F — Integration and release
### TASK 31 — End-to-end onboarding test
Automate complete fresh-session path through first My Taste and Home using fixtures/mocked YouTube.
**DoD:** no broken route/state transition.

### TASK 32 — End-to-end retention loop test
Test returning completed session -> Home -> like/dislike/save/skip -> My Taste/Discover/Search/Saved.
**DoD:** persisted feedback behaves per spec.

### TASK 33 — Docker/dev setup hardening
Add Docker-compatible local setup, health checks, startup docs, env validation.
**DoD:** clean machine/containerized flow documented and reproducible.

### TASK 34 — Security/compliance pass
Review secrets, CORS/cookies, YouTube embedding/media rules, stale metadata handling, error logging.
**DoD:** no secrets committed; no media download path; production-safe cookie config documented.

### TASK 35 — Production build/readiness
Run backend tests/lint, frontend lint/build, migration-from-empty smoke test, final demo flow.
**DoD:** all checks pass; known limitations documented.

## Scope rule
Do not bundle multiple numbered tasks unless the user explicitly requests it. Small prerequisite fixes are allowed; unrelated refactors are not.
