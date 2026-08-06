# JobLens — Job Market Transparency

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

JobLens collects technology job postings over time and estimates **Active Hiring Confidence** from observable signals such as recency, repeated sightings, parallel advertisements, repost history, compensation disclosure, applicants, and company behavior.

The score estimates posting activity. It is not proof of employer intent.

## Current behavior

- Collects Simplify directly from its public feeds. Simplify never consumes JSearch requests.
- Uses one generic JSearch collection pass to retrieve mixed publishers instead of spending separate requests on LinkedIn, Indeed, ZipRecruiter, Glassdoor, and other targeted searches.
- Adds `-site:simplify.jobs` to JSearch queries and removes any Simplify publisher/apply options returned by the provider.
- Stores `collection_provider=jsearch` separately from the actual publisher in `source`.
- Preserves `job_publisher`, every distinct `apply_options` publisher/link, and direct-company application URLs.
- Updates repeated copies of the same JSearch `job_id` instead of inserting duplicate posting rows.
- Keeps different source IDs separate until identity analysis classifies them as `original`, `parallel`, or `repost` and assigns a shared `canonical_job_id` when appropriate.
- Returns one representative card per canonical opening by default and exposes every known board/application URL in `canonical_sources`.
- Displays linked **Found on** chips in the frontend. Multiple links from one publisher remain accessible and are numbered; direct employer links are marked **Direct**.
- Enforces a Redis-backed monthly JSearch request budget before every request attempt, including retries.
- Reconciles provider quota-response headers as a second guard and persists counters through Redis AOF storage.
- Removes per-posting geocoding and model generation from collection. Optional enrichment runs separately.
- Acts on Simplify's own closed/inactive signal: a listing the feed reports as closed deactivates the matching existing row (with a recorded reason) instead of being silently dropped.
- Tracks title-derived specialization tags, including a best-effort security-clearance signal, and exposes a `clearance_required` filter on the jobs API and frontend.
- Records a traceable event when a re-observed listing's location, work arrangement, or employment type changes, invalidating its score instead of updating silently.

## Pipeline

```text
Simplify public feeds ─────────────────────────────────────────┐
                                                               ├─→ normalization
JSearch /search-v2 → publisher + apply-link attribution ───────┘
  → batched PostgreSQL ingestion
  → optional cached enrichment
  → canonical identity/history analysis
  → Active Hiring Confidence scoring
  → FastAPI / Next.js
```

## Exact JSearch API-key location

Put the **OpenWeb Ninja API key** in:

```text
backend/.env
```

Or, from the repository root:

```text
backend/.env
```

Open it from the repository root with:

```bash
open -e backend/.env
```

Add or replace this line:

```env
OPENWEBNINJA_API_KEY=your_openwebninja_key_here
```

Do not add quotes or spaces. Do not place the key in `.env.example`, `docker-compose.yml`, source code, screenshots, commits, or GitHub.

Recommended JSearch Pro settings in the same `backend/.env` file:

```env
ENABLED_SCRAPER_SOURCES=simplify,jsearch
OPENWEBNINJA_API_KEY=your_openwebninja_key_here

JSEARCH_PAGES_PER_QUERY=10
JSEARCH_SCHEDULE_EVERY_HOURS=24
JSEARCH_MONTHLY_REQUEST_LIMIT=10000
JSEARCH_REQUEST_RESERVE=1400
JSEARCH_QUERIES=software engineer,data analyst,data engineer,data scientist,machine learning engineer,product manager,security engineer
JSEARCH_COUNTRY=us
JSEARCH_LANGUAGE=en
JSEARCH_LOCATION=United States
JSEARCH_DATE_POSTED=month
JSEARCH_EXCLUDED_PUBLISHERS=simplify,simplifyjobs,simplify jobs
JSEARCH_EXCLUDED_DOMAINS=simplify.jobs
ALLOW_OVERLAPPING_JSEARCH_SOURCES=false
```

Use a dedicated OpenWeb Ninja API key for JobLens and do not use that key for unrelated manual requests. Requests made outside JobLens still count against the same provider quota.

## JSearch Pro request protection

Default schedule mathematics:

```text
7 role queries × 10 cursor pages × 1 run/day × 31 days
= 2,170 planned requests in a 31-day month
```

The code also applies these protections:

1. Every JSearch HTTP attempt reserves one unit in Redis before it is sent. Retries count.
2. JobLens stops at `10,000 - 1,000 = 9,000` locally counted attempts.
3. OpenWeb Ninja rate-limit headers are saved and collection stops when provider-reported remaining requests reach the 1,000-request reserve.
4. Configuration validation prevents a scheduled generic JSearch plan whose estimated usage exceeds the protected application budget.
5. Generic `jsearch` cannot be scheduled together with targeted `linkedin` or `indeed` unless overlap is explicitly enabled.
6. All JSearch-backed adapters share one provider lock, preventing concurrent generic/targeted runs.
7. Redis uses append-only persistence so an ordinary container restart does not discard the counter.

With the default daily schedule and roughly ten returned rows per page, the theoretical ceiling is about **21,700 returned rows/month**. It is not a guarantee of 21,700 unique jobs: short pages, repeated daily sightings, overlapping role queries, and the same opening appearing on several boards reduce the unique count.

## Quick start

```bash
cd ~/Desktop/Bravo_Transparency_Jobs

test -f backend/.env || cp backend/.env.example backend/.env
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
docker compose exec backend alembic current
```

The migration head should be:

```text
0006_source_sighting_links
```

The one-shot `migrate` service runs `alembic upgrade head` before the backend, worker, and Beat services start. `alembic current` only verifies the installed revision.

Verify the worker received the key without printing it:

```bash
docker compose exec worker sh -c \
  'test -n "$OPENWEBNINJA_API_KEY" && echo "OPENWEBNINJA_API_KEY is set" || echo "OPENWEBNINJA_API_KEY is missing"'
```

## Controlled first JSearch test

Keep Beat stopped and use only one page per query. This spends at most about seven requests plus any retries:

```bash
docker compose stop beat

docker compose exec worker celery -A app.workers.celery_app inspect active

docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["jsearch",1]'

docker compose logs -f worker
```

Look for:

```text
scraper_complete
jsearch_quota_status
ingest_progress
task_complete
```

Run a full configured collection after the test succeeds:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["jsearch"]'
```

Check the protected quota at any time:

```bash
docker compose exec worker python -m app.scripts.jsearch_quota
```

## Source attribution

Inspect primary posting publishers:

```bash
docker compose exec postgres psql -U joblens -d joblens -c "
SELECT collection_provider, source, COUNT(*)
FROM job_postings
GROUP BY collection_provider, source
ORDER BY COUNT(*) DESC;"
```

Inspect every application link:

```bash
docker compose exec postgres psql -U joblens -d joblens -c "
SELECT source, publisher_name, is_direct, COUNT(*)
FROM job_source_sightings
GROUP BY source, publisher_name, is_direct
ORDER BY COUNT(*) DESC;"
```

The jobs endpoint collapses canonical duplicates by default:

```text
GET /api/v1/jobs/?collapse_canonical=true
```

Each result includes every known board/link:

```json
{
  "source": "linkedin",
  "collection_provider": "jsearch",
  "canonical_sources": [
    {"source": "linkedin", "publisher_name": "LinkedIn", "source_url": "...", "is_direct": false},
    {"source": "indeed", "publisher_name": "Indeed", "source_url": "...", "is_direct": false},
    {"source": "company_site", "publisher_name": "Acme Careers", "source_url": "...", "is_direct": true}
  ]
}
```

Request every underlying posting row with:

```text
GET /api/v1/jobs/?collapse_canonical=false
```

## Determine hiring activity

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.analyze_hiring_activity --args='[1000]'
```

Continue scoring until `remaining_unscored` is zero:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.score_all_jobs --args='[1000, false]'
```

A first observation establishes a baseline. Repeated daily collection is what adds evidence about persistence, changes, closures, parallel advertisements, and later reposts.

## Safe enrichment defaults

```env
GEOCODING_ENABLED=false
DESCRIPTION_EMBEDDINGS_ENABLED=false
SEMANTIC_TITLE_MATCHING_ENABLED=false
IDENTITY_CANDIDATE_LIMIT=100
AUTO_EXPIRE_STALE_JOBS=false
```

## Tests

```bash
cd backend
pytest -q
```

```bash
cd frontend
npm ci
npm run type-check
npm run lint
npm run build
```

See `docs/ARCHITECTURE.md`, `docs/deployment.md`, `docs/sources/jsearch.md`, `docs/source_attribution.md`, and `docs/scraper_reliability.md`.
