# JobLens Changelog

## v0.2.0 — Full audit & source expansion

### Files Created

| File | Purpose |
|------|---------|
| `backend/app/workers/scrapers/base.py` | `BaseScraperAdapter` interface — all scrapers inherit from this |
| `backend/app/workers/scrapers/linkedin.py` | LinkedIn adapter (JSearch / official API / Playwright) |
| `backend/app/workers/scrapers/glassdoor.py` | Glassdoor adapter (RapidAPI) |
| `backend/app/workers/scrapers/ziprecruiter.py` | ZipRecruiter Publisher API adapter |
| `backend/app/workers/scrapers/dice.py` | Dice public API adapter (no key required) |
| `backend/app/workers/scrapers/monster.py` | Monster adapter (RapidAPI) |
| `backend/app/workers/scrapers/jobright.py` | Jobright API adapter |
| `backend/app/workers/scrapers/simplify.py` | Simplify GitHub JSON feed adapter (no key required) |
| `docs/sources/indeed.md` | Indeed integration guide |
| `docs/sources/linkedin.md` | LinkedIn integration guide + 3 methods |
| `docs/sources/glassdoor.md` | Glassdoor integration guide |
| `docs/sources/ziprecruiter.md` | ZipRecruiter integration guide |
| `docs/sources/dice.md` | Dice integration guide |
| `docs/sources/monster.md` | Monster integration guide |
| `docs/sources/jobright.md` | Jobright integration guide |
| `docs/sources/simplify.md` | Simplify integration guide |
| `docs/dependency_map.md` | Full dependency graph (backend + frontend + infra) |
| `docs/changelog.md` | This file |
| `frontend/tsconfig.json` | TypeScript compiler config |
| `frontend/postcss.config.js` | PostCSS for Tailwind |
| `frontend/src/styles/globals.css` | Tailwind base + utility classes |
| `frontend/src/pages/_app.tsx` | Next.js app wrapper |
| `frontend/src/pages/index.tsx` | Starter home page wired to API |
| `infrastructure/nginx/nginx.conf` | Nginx reverse proxy (self-hosted) |
| `backend/pytest.ini` | pytest config |
| `backend/.dockerignore` | Docker build context exclusions |
| `frontend/.dockerignore` | Docker build context exclusions |

### Files Modified

| File | What changed |
|------|-------------|
| `.gitignore` | Full rewrite: added HuggingFace cache, `.next/`, `node_modules/`, JetBrains, Docker volumes, sentence-transformers, logs, Playwright, Celery, Redis |
| `backend/.env.example` | Added all 8 source-specific API keys + LinkedIn mode config |
| `backend/app/core/config.py` | Added all source env vars as typed settings fields |
| `backend/app/models/models.py` | Added `JobEvent` table, `JobEmbedding` table (standalone), `EventType` enum; added `source` + `description_raw` + `description_hash` to `JobSnapshot`; added `activity_score`, `description_change_score`, `applicant_trend`, `salary_trend` to `JobPosting` |
| `backend/migrations/0001_initial.py` | Updated to match new schema: `job_events`, `job_embeddings`, updated `job_snapshots` |
| `backend/alembic.ini` | Removed hardcoded `localhost` URL — URL is now set dynamically from env in `migrations/env.py` |
| `backend/requirements.txt` | Added `feedparser`, `lxml`, `torch`, `transformers`, `psycopg2-binary`, `pytest-asyncio` |
| `backend/app/schemas/jobs.py` | Added `JobEventOut`; added analytics fields to list/detail schemas |
| `backend/app/services/scoring.py` | Added `activity_score`, `description_change_score`, `applicant_trend`, `salary_trend` computation |
| `backend/app/workers/celery_app.py` | Rewired to universal `scrape_source` task dispatching all 8 scrapers; staggered beat schedule to avoid rate limit collisions |
| `backend/app/workers/ingestion.py` | Added event firing (`created`, `applicant_spike`, `description_changed`); embedding now written to standalone `job_embeddings` table; snapshots now include `source` + `description_raw` + `description_hash` |
| `backend/app/workers/scrapers/__init__.py` | Rewrote as full scraper registry with `SCRAPER_REGISTRY` dict |
| `backend/app/api/routes/jobs.py` | Added `activity_score` and `competition_score` to valid sort columns |
| `backend/app/main.py` | Bumped version to 0.2.0; health endpoint now lists all 8 sources |
| `backend/tests/test_core.py` | Added `activity_score` tests, expanded normalizer coverage |
| `frontend/src/types/jobs.ts` | All 8 sources in `JobSource`; added `SOURCE_LABELS`, `SOURCE_COLORS`; added `JobEvent` interface; added analytics fields |
| `docker-compose.yml` | Added `hf_cache` volume shared across backend/worker/beat; added `env_file` for `.env`; added restart policies |
| `README.md` | Full rewrite: all 8 sources in table, activation priority, full schema table, GitHub Desktop gitignore instructions |

### Remaining gaps (backlog)

- Frontend components not yet built (job card, filter panel, stats dashboard) — scaffold only
- Company rating enrichment task (Glassdoor company endpoint) — not yet a scheduled task
- LinkedIn Playwright mode — adapter exists, proxy rotation not implemented
- Email/webhook alerts for watched jobs — `watched_jobs` table not yet created
- Salary benchmark seeding only has US-wide data — metro-specific data needs a data source
- `activity_score` on `Company` model — currently computed per-posting but not aggregated back to company level

## v0.3.0 — Structured identity and Active Hiring Confidence

- Added tech-focused `decompose_title()` with job family, seniority, specialization, and parse confidence.
- Added structured identity fingerprints and canonical listing groups.
- Reworked ingestion to update only stable source records, preserving simultaneous parallel openings.
- Added original/parallel/repost classification with remote and multi-location handling.
- Added configurable parallel-listing and repost-gap windows.
- Added Active Hiring Confidence to scoring, API schemas, filters, sorting, stats, and frontend display.
- Added Alembic migration `0002_structured_identity.py`.
- Expanded identity and classifier tests.
- Corrected the Jobright Celery beat schedule.
