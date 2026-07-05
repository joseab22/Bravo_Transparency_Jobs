# JobLens — Job Market Transparency Tracker

A labor market intelligence platform that surfaces hidden hiring signals across 8 job boards:
**active hiring confidence · structured identity · repost detection · cross-platform tracking · salary transparency**

---

## What it does

| Signal | How |
|--------|-----|
| Ghost job probability | Weighted model: repost count, days active, applicant volume, salary listing, company rating, similar history |
| Structured identity | Tech-focused title decomposition into job family, seniority, and specialization |
| Parallel vs. repost detection | Stable source IDs, timing, active state, remote/location scope, and semantic fallback |
| Active Hiring Confidence | Positive-facing score combining freshness, activity, related openings, and ghost-job signals |
| Cross-platform tracking | Tracks every platform a job appears on via `job_source_sightings` |
| Salary fairness | Compares posted salary to `salary_benchmarks` (p50 by title + metro + seniority) |
| Applicant trend | Slope of applicant count over time from `job_snapshots` |
| Description change score | SHA-256 diff across snapshot history — title/description rewrites are a ghost signal |
| Activity score | Composite hiring velocity signal per posting |
| Scraper reliability | Shared `429`/`Retry-After` backoff, jitter, transient-error retries, and Redis per-source locks |

---

## Job Sources

| Source | Adapter | Method | Key Required |
|--------|---------|--------|-------------|
| **Indeed** | `scrapers/indeed.py` | JSearch RapidAPI | `RAPIDAPI_KEY` |
| **LinkedIn** | `scrapers/linkedin.py` | JSearch RapidAPI (default) or official API | `RAPIDAPI_KEY` |
| **Glassdoor** | `scrapers/glassdoor.py` | RapidAPI Glassdoor | `RAPIDAPI_KEY` |
| **ZipRecruiter** | `scrapers/ziprecruiter.py` | Publisher API (free) | `ZIPRECRUITER_API_KEY` |
| **Dice** | `scrapers/dice.py` | Public API | None required |
| **Monster** | `scrapers/monster.py` | RapidAPI Monster | `RAPIDAPI_KEY` |
| **Jobright** | `scrapers/jobright.py` | Jobright API | `JOBRIGHT_API_KEY` |
| **Simplify** | `scrapers/simplify.py` | Public GitHub JSON feed | None required |

See `docs/sources/` for per-source setup guides.

**Activation priority:** Start with Dice (no key) + Simplify (no key) → then add `RAPIDAPI_KEY` (unlocks Indeed, LinkedIn, Glassdoor, Monster) → then ZipRecruiter publisher key → then Jobright.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI 0.111 (Python 3.11) |
| Database | PostgreSQL 15 + pgvector |
| Background jobs | Celery 5.3 + Redis 7 |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (384-dim) |
| Frontend | Next.js 14 + Tailwind CSS |
| Infrastructure | Docker Compose (dev) · Railway + Vercel (prod) |
| CI/CD | GitHub Actions |

---

## Project Structure

```
Bravo_Transparency_Jobs/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI route handlers
│   │   │   ├── jobs.py          # GET /jobs, GET /jobs/{id}, GET /jobs/stats
│   │   │   └── companies.py     # GET /companies, GET /companies/{id}/jobs
│   │   ├── core/
│   │   │   └── config.py        # All env var settings (pydantic-settings)
│   │   ├── db/
│   │   │   └── session.py       # Async SQLAlchemy engine + session
│   │   ├── models/
│   │   │   └── models.py        # ORM: Company, JobPosting, JobSnapshot,
│   │   │                        #   JobEvent, JobEmbedding, JobSkill,
│   │   │                        #   RepostEvent, JobSourceSighting, SalaryBenchmark
│   │   ├── schemas/
│   │   │   └── jobs.py          # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── normalizer.py    # Structured title decomposition + identity keys
│   │   │   ├── repost_detector.py  # Original/parallel/repost classification
│   │   │   └── scoring.py       # Ghost prob, health, competition, salary fairness
│   │   ├── workers/
│   │   │   ├── celery_app.py    # Beat schedule + Redis per-source scrape locks
│   │   │   ├── ingestion.py     # Upsert pipeline + event firing + embeddings
│   │   │   └── scrapers/
│   │   │       ├── base.py      # Shared HTTP retry and rate-limit handling
│   │   │       ├── indeed.py    #  JSearch API
│   │   │       ├── linkedin.py  #  JSearch / official API / Playwright
│   │   │       ├── glassdoor.py #  RapidAPI Glassdoor
│   │   │       ├── ziprecruiter.py #  Publisher API
│   │   │       ├── dice.py      #  Public API (no key)
│   │   │       ├── monster.py   # RapidAPI Monster
│   │   │       ├── jobright.py  #  Jobright API
│   │   │       └── simplify.py  #  GitHub JSON feed (no key)
│   │   └── scripts/
│   │       └── seed.py          # Seed salary benchmarks
│   ├── migrations/
│   │   ├── env.py               # Alembic async env
│   │   └── versions/
│   │       ├── 0001_initial.py  # Initial schema
│   │       └── 0002_structured_identity.py  # Identity + hiring confidence fields
│   ├── tests/
│   │   └── test_core.py         # Unit tests: normalizer, scoring
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example             # All env vars documented
├── frontend/
│   └── src/
│       ├── pages/               # Next.js pages (_app.tsx, index.tsx)
│       ├── styles/globals.css   # Tailwind base styles
│       ├── types/jobs.ts        # TypeScript interfaces
│       └── lib/api.ts           # Axios API client
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.backend
│   │   └── Dockerfile.frontend
│   ├── nginx/nginx.conf         # Reverse proxy (self-hosted)
│   └── scripts/init_db.sql     # pgvector + pg_trgm extensions
├── docs/
│   ├── deployment.md            # Railway / Render / VPS setup
│   ├── change_tracking.md       # How job changes are tracked + SQL queries
│   ├── identity_resolution.md      # Structured identity and repost rules
│   ├── scraper_reliability.md      # Backoff and duplicate-task protection
│   ├── validation.md               # Validation record
│   └── sources/                 # Per-source integration guides
│       ├── indeed.md · linkedin.md · glassdoor.md · ziprecruiter.md
│       └── dice.md · monster.md · jobright.md · simplify.md
├── .github/workflows/
│   ├── ci.yml                   # Test + build on every push
│   └── deploy.yml               # Deploy to Railway + Vercel on main
├── docker-compose.yml
└── .gitignore
```

---

## Quickstart

### Prerequisites
- Docker Desktop (includes Docker Compose)
- Git

### Run locally

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/Bravo_Transparency_Jobs.git
cd Bravo_Transparency_Jobs

# Copy env files and fill in your values
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# Start all services — migrations run automatically on first boot
docker compose up -d

# Seed salary benchmark data (first time only)
docker compose exec backend python -m app.scripts.seed

# Verify the API is up
curl http://localhost:8000/api/v1/jobs/
# → {"total":0,"page":1,"page_size":20,"pages":0,"results":[]}
```

API docs: `http://localhost:8000/docs`
Frontend: `http://localhost:3000`

> **Note:** Migrations run automatically when the backend container starts.
> You do not need to run `alembic upgrade head` manually.

---

### Activate scrapers

```bash
# Dice and Simplify require no API key — start here
docker compose exec worker celery -A app.workers.celery_app call joblens.scrape_source --args '["dice"]'
docker compose exec worker celery -A app.workers.celery_app call joblens.scrape_source --args '["simplify"]'

# Add RAPIDAPI_KEY to backend/.env to unlock Indeed, LinkedIn, Glassdoor, Monster
# Then restart the worker to pick up the new key:
docker compose restart worker beat

# Add ZIPRECRUITER_API_KEY for ZipRecruiter (best salary data coverage)
# Add JOBRIGHT_API_KEY after requesting access at jobright.ai
```

Celery Beat runs staggered source schedules once keys are configured. Simplify runs daily; most other sources run every six hours. Per-source Redis locks prevent overlapping runs.

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `companies` | Company master record with rating + hiring metrics |
| `job_postings` | Posting observations, canonical grouping, listing classification, and transparency scores |
| `job_snapshots` | Point-in-time history (applicants, salary, description per source) |
| `job_events` | Audit log of all state changes (created, reposted, applicant_spike, etc.) |
| `job_embeddings` | 384-dim sentence-transformer vectors (ivfflat indexed) |
| `job_skills` | Normalized skills per posting |
| `repost_events` | Verified repost occurrence log tied to a canonical job chain |
| `job_source_sightings` | Every platform a job has been seen on |
| `salary_benchmarks` | Market p25/p50/p75 by title + metro + seniority |

### Ghost job probability formula

```
P(ghost) = 0.30 × repost_score
         + 0.25 × days_active_score
         + 0.15 × applicant_score
         + 0.10 × salary_score
         + 0.10 × company_rating_score
         + 0.10 × historical_repost_score
```

All weights are configurable via environment variables.

---

## Deployment

See `docs/deployment.md` for Railway + Vercel (recommended) and self-hosted VPS options.

---

## License

MIT
