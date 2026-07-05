# Next Steps: Collect and Analyze Hiring Activity

## 1. Merge into the existing Git repository

Extract the audited archive beside the existing repository, then copy its contents without replacing `.git` or the private environment file:

```bash
rsync -av \
  --exclude='.git' \
  --exclude='backend/.env' \
  Bravo_Transparency_Jobs-audited/ \
  ~/Desktop/Bravo_Transparency_Jobs/
```

Keep the existing `backend/.env`. Compare it with `.env.example` and add these safe defaults when missing:

```env
ENABLED_SCRAPER_SOURCES=simplify
GEOCODING_ENABLED=false
DESCRIPTION_EMBEDDINGS_ENABLED=false
SEMANTIC_TITLE_MATCHING_ENABLED=false
IDENTITY_CANDIDATE_LIMIT=100
AUTO_EXPIRE_STALE_JOBS=false
```

## 2. Rebuild and verify

```bash
cd ~/Desktop/Bravo_Transparency_Jobs
docker compose down
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
docker compose exec backend alembic current
```

Expected migration head:

```text
0003_location_cache
```

## 3. Run one controlled scrape

```bash
docker compose stop beat
docker compose exec worker celery -A app.workers.celery_app purge -f
docker compose exec worker celery -A app.workers.celery_app inspect active
```

The active list should be empty. Trigger Simplify once:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["simplify"]'
```

Follow progress:

```bash
docker compose logs -f worker
```

Look for `simplify_feed_fetched`, `ingest_progress`, and `task_complete`. Press `Ctrl+C` only to stop following logs.

## 4. Confirm database population

```bash
docker compose exec postgres psql -U joblens -d joblens -c \
  "SELECT source, COUNT(*) FROM job_postings GROUP BY source ORDER BY COUNT(*) DESC;"
```

```bash
docker compose exec postgres psql -U joblens -d joblens -c \
  "SELECT id, title_raw, source, location_raw, date_first_seen FROM job_postings ORDER BY id DESC LIMIT 20;"
```

## 5. Classify history and score activity

Run the identity pass and first scoring batch:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.analyze_hiring_activity --args='[1000]'
```

Follow the result in worker logs:

```bash
docker compose logs -f worker
```

Continue scoring in batches until the task result reports `remaining_unscored: 0`:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.score_all_jobs --args='[1000, false]'
```

Inspect classifications:

```bash
docker compose exec postgres psql -U joblens -d joblens -c \
  "SELECT listing_classification, COUNT(*) FROM job_postings GROUP BY listing_classification ORDER BY COUNT(*) DESC;"
```

Inspect high-confidence active listings:

```bash
docker compose exec postgres psql -U joblens -d joblens -c "
SELECT title_raw,
       source,
       listing_classification,
       ROUND(active_hiring_confidence::numeric, 1) AS hiring_confidence,
       ROUND(ghost_confidence::numeric, 3) AS evidence_confidence,
       ROUND(ghost_job_probability::numeric, 3) AS ghost_probability,
       days_active
FROM job_postings
WHERE active_hiring_confidence IS NOT NULL
ORDER BY active_hiring_confidence DESC
LIMIT 25;"
```

## 6. Begin repeated observation

```bash
docker compose start beat
```

A first scrape establishes a baseline. Repeated scheduled sightings add snapshots and reveal persistence, changes, closures, parallel openings, and later reposts. Once scheduled collection has proven reliable, set `AUTO_EXPIRE_STALE_JOBS=true` to allow postings unseen for `STALE_JOB_DAYS` to become inactive.
