# JobLens — Job Market Transparency Tracker

A labor market intelligence platform that surfaces hidden hiring signals across 8 job boards:
**ghost job probability · repost detection · cross-platform tracking · salary fairness scoring**

---

## What it does

| Signal | How |
|--------|-----|
| Ghost job probability | Weighted model: repost count, days active, applicant volume, salary listing, company rating, similar history |
| Repost detection | Identity key matching (`company + normalized_title + metro`) + cosine similarity on descriptions |
| Cross-platform tracking | Tracks every platform a job appears on via `job_source_sightings` |
| Salary fairness | Compares posted salary to `salary_benchmarks` (p50 by title + metro + seniority) |
| Applicant trend | Slope of applicant count over time from `job_snapshots` |
| Description change score | SHA-256 diff across snapshot history — title/description rewrites are a ghost signal |
| Activity score | Composite hiring velocity signal per company |

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

**Activation priority:** Start with Dice (no key) + Simplify (no key) → then add RAPIDAPI_KEY (unlocks Indeed, LinkedIn, Glassdoor, Monster) → then ZipRecruiter publisher key → then Jobright.

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
job-tracker/
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
│   │   │   ├── normalizer.py    # Title/location/skill normalization + identity key
│   │   │   ├── repost_detector.py  # Repost detection + sentence-transformers
│   │   │   └── scoring.py       # Ghost prob, health, competition, salary fairness
│   │   ├── workers/
│   │   │   ├── celery_app.py    # Celery app + beat schedule (all 8 scrapers)
│   │   │   ├── ingestion.py     # Upsert pipeline + event firing + embeddings
│   │   │   └── scrapers/
│   │   │       ├── base.py      # BaseScraperAdapter interface
│   │   │       ├── indeed.py    # ✅ JSearch API
│   │   │       ├── linkedin.py  # ✅ JSearch / official API / Playwright
│   │   │       ├── glassdoor.py # ✅ RapidAPI Glassdoor
│   │   │       ├── ziprecruiter.py # ✅ Publisher API
│   │   │       ├── dice.py      # ✅ Public API (no key)
│   │   │       ├── monster.py   # ✅ RapidAPI Monster
│   │   │       ├── jobright.py  # ✅ Jobright API
│   │   │       └── simplify.py  # ✅ GitHub JSON feed (no key)
│   │   └── scripts/
│   │       └── seed.py          # Seed salary benchmarks
│   ├── migrations/
│   │   ├── env.py               # Alembic async env
│   │   └── 0001_initial.py      # Full schema migration
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
│   └── sources/                 # Per-source integration guides
│       ├── indeed.md · linkedin.md · glassdoor.md · ziprecruiter.md
│       ├── dice.md · monster.md · jobright.md · simplify.md
├── .github/workflows/
│   ├── ci.yml                   # Test + build on every push
│   └── deploy.yml               # Deploy to Railway + Vercel on main
├── docker-compose.yml
└── .gitignore                   # Python · Node · Docker · JetBrains · HuggingFace
```

---

## Quickstart

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- Node.js 18+

### Run locally

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/joblens.git && cd joblens

# Copy env files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# Start all services (postgres + redis + api + worker + beat + frontend)
docker compose up -d

# Run migrations
docker compose exec backend alembic upgrade head

# Seed salary benchmarks
docker compose exec backend python -m app.scripts.seed

# Frontend (if not using Docker for frontend dev)
cd frontend && npm install && npm run dev
```

API: `http://localhost:8000/docs`  
App: `http://localhost:3000`

### Activate scrapers (minimum config)

```bash
# Step 1: No keys needed — Dice and Simplify work immediately
docker compose exec worker celery -A app.workers.celery_app call joblens.scrape_source --args '["dice"]'
docker compose exec worker celery -A app.workers.celery_app call joblens.scrape_source --args '["simplify"]'

# Step 2: Add RAPIDAPI_KEY to .env, then restart worker — unlocks Indeed, LinkedIn, Glassdoor, Monster
docker compose restart worker beat

# Step 3: Add ZIPRECRUITER_API_KEY for ZipRecruiter (best salary data)
# Step 4: Add JOBRIGHT_API_KEY after requesting access at jobright.ai
```

---

## Database Schema

### Core tables

| Table | Purpose |
|-------|---------|
| `companies` | Company master record with rating + hiring metrics |
| `job_postings` | Canonical job record with all transparency scores |
| `job_snapshots` | Point-in-time history (applicants, salary, description per source) |
| `job_events` | Audit log of all state changes (created, reposted, applicant_spike, etc.) |
| `job_embeddings` | 384-dim sentence-transformer vectors (separate table, ivfflat indexed) |
| `job_skills` | Normalized skills per posting |
| `repost_events` | Repost occurrence log tied to `job_identity_key` |
| `job_source_sightings` | Every platform a job has been seen on |
| `salary_benchmarks` | Market p25/p50/p75 by title + metro + seniority |

### Ghost job probability formula

```
P(ghost) = 0.30 × repost_score
         + 0.25 × days_active_score
         + 0.15 × applicant_score
         + 0.10 × salary_score       (no salary listed → higher risk)
         + 0.10 × company_rating_score
         + 0.10 × historical_repost_score
```

Weights are configurable via env vars.

---

## Deployment

See `docs/deployment.md` for Railway + Vercel (recommended) and self-hosted VPS options.

---

## GitHub Desktop `.gitignore` setup

1. In GitHub Desktop → **Repository → Repository Settings → Ignored Files**
2. Or when creating the repo: choose **Python** as the template
3. Replace the generated `.gitignore` with the one in this repo (it covers Python + Node + Docker + JetBrains + VS Code + HuggingFace model caches)

---

## License

MIT
