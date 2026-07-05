# JobLens — Job Market Transparency

JobLens collects technology job postings over time and estimates **Active Hiring Confidence** from observable signals such as posting recency, repeated sightings, parallel openings, repost history, compensation disclosure, applicants, and company behavior.

The score is an estimate of posting activity—not proof of employer intent.

## What changed in this audited release

- Centralized tech-title decomposition into job family, seniority, and specialization.
- Preserves separate source listings instead of collapsing simultaneous openings.
- Classifies listings as `original`, `parallel`, or `repost` after collection.
- Handles remote and multi-location advertisements independently from repost detection.
- Removes per-job geocoding from all scraper parsers.
- Adds cached, opt-in geocoding for unique locations.
- Adds shared HTTP retries, `Retry-After`, exponential backoff, jitter, and source locks.
- Prefetches stable IDs and companies, commits large feeds in batches, and throttles unchanged snapshots.
- Keeps semantic title matching and description embeddings opt-in so analysis does not download a model unexpectedly.
- Moves embeddings and scoring into deliberate background analysis tasks.
- Aligns ORM models, API schemas, frontend types, Alembic migrations, tests, and documentation.

## Architecture

```text
Job source
  → rate-limited scraper
  → pure normalization
  → batched PostgreSQL ingestion
  → optional cached location/embedding enrichment
  → identity-history classification
  → Active Hiring Confidence scoring
  → FastAPI / Next.js
```

## Quick start

```bash
cp backend/.env.example backend/.env
```

When using Docker, Compose supplies the correct internal database and Redis hostnames. API keys can remain blank for disabled sources.

```bash
docker compose down
docker compose up -d --build
docker compose ps
```

Verify:

```bash
curl http://localhost:8000/health
docker compose exec backend alembic current
```

The migration head should be:

```text
0003_location_cache
```

## Safe first scrape

Stop automatic scheduling during manual testing:

```bash
docker compose stop beat
docker compose exec worker celery -A app.workers.celery_app purge -f
```

Trigger Simplify once:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["simplify"]'
```

Watch progress:

```bash
docker compose logs -f worker
```

Check database population:

```bash
docker compose exec postgres psql -U joblens -d joblens \
  -c "SELECT source, COUNT(*) FROM job_postings GROUP BY source ORDER BY COUNT(*) DESC;"
```

## Determine hiring activity

After collection completes, run identity classification and the first scoring batch:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.analyze_hiring_activity --args='[1000]'
```

Continue scoring until the worker result reports `remaining_unscored: 0`:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.score_all_jobs --args='[1000, false]'
```

A single scrape produces a preliminary score. Repeated daily sightings, snapshot changes, closures, and later reappearances make the history-based signals more informative.

Inspect results:

```bash
docker compose exec postgres psql -U joblens -d joblens -c "
SELECT title_raw, source, listing_classification,
       ROUND(active_hiring_confidence::numeric, 1) AS hiring_confidence,
       ROUND(ghost_job_probability::numeric, 3) AS ghost_probability,
       days_active
FROM job_postings
WHERE active_hiring_confidence IS NOT NULL
ORDER BY active_hiring_confidence DESC
LIMIT 25;"
```

Open:

- Frontend: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`

Restart scheduling after the manual test:

```bash
docker compose start beat
```

## Source configuration

Only sources in `ENABLED_SCRAPER_SOURCES` are scheduled. The default is:

```env
ENABLED_SCRAPER_SOURCES=simplify
```

Other adapters require valid credentials and verified provider contracts. Add them individually after testing one source at a time.

## Enrichment defaults

These are disabled by default because they are expensive or externally rate-limited:

```env
GEOCODING_ENABLED=false
DESCRIPTION_EMBEDDINGS_ENABLED=false
SEMANTIC_TITLE_MATCHING_ENABLED=false
IDENTITY_CANDIDATE_LIMIT=100
```

Geocoding operates on cached **unique locations**, not every job posting. Semantic title matching can be enabled later, but structured title fields and bounded lexical matching are the safe default for large collections.

`AUTO_EXPIRE_STALE_JOBS=false` is also conservative during initial testing. After scheduled collection has run reliably for several days, enable it to let postings that have not been seen for the configured stale period become inactive.

## Tests

```bash
cd backend
pytest tests -q
```

```bash
cd frontend
npm ci
npm run type-check
npm run lint
npm run build
```

See `docs/next_steps.md`, `docs/validation.md`, `docs/identity_resolution.md`, and `docs/scraper_reliability.md` for implementation details.
