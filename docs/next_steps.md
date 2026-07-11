# Next Steps: JSearch Pro Collection and Hiring Analysis

## 1. Merge the updated repository

```bash
rsync -av \
  --exclude='.git' \
  --exclude='backend/.env' \
  Bravo_Transparency_Jobs-jsearch-pro/ \
  ~/Desktop/Bravo_Transparency_Jobs/
```

Your existing PostgreSQL Docker volume and private `backend/.env` remain untouched.

## 2. Put the JSearch key in the correct file

Open:

```bash
open -e ~/Desktop/Bravo_Transparency_Jobs/backend/.env
```

Set:

```env
RAPIDAPI_KEY=your_rotated_private_key_here
```

The exact path is:

```text
/Users/josebravo/Desktop/Bravo_Transparency_Jobs/backend/.env
```

Do not place the key in `.env.example` or GitHub.

Add these settings:

```env
ENABLED_SCRAPER_SOURCES=simplify,jsearch
JSEARCH_PAGES_PER_QUERY=10
JSEARCH_SCHEDULE_EVERY_HOURS=24
JSEARCH_MONTHLY_REQUEST_LIMIT=10000
JSEARCH_REQUEST_RESERVE=1000
JSEARCH_QUERIES=software engineer,data analyst,data engineer,data scientist,machine learning engineer,product manager,security engineer
JSEARCH_COUNTRY=us
JSEARCH_LANGUAGE=en
JSEARCH_LOCATION=United States
JSEARCH_DATE_POSTED=month
JSEARCH_EXCLUDED_PUBLISHERS=simplify,simplifyjobs,simplify jobs
JSEARCH_EXCLUDED_DOMAINS=simplify.jobs
ALLOW_OVERLAPPING_JSEARCH_SOURCES=false

GEOCODING_ENABLED=false
DESCRIPTION_EMBEDDINGS_ENABLED=false
SEMANTIC_TITLE_MATCHING_ENABLED=false
AUTO_EXPIRE_STALE_JOBS=false
```

## 3. Rebuild and verify the migration

```bash
cd ~/Desktop/Bravo_Transparency_Jobs
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
docker compose exec backend alembic current
```

Expected head:

```text
0006_source_sighting_links
```

The backend startup runs `alembic upgrade head`; `current` is verification only.

Verify the key reached the worker without displaying it:

```bash
docker compose exec worker sh -c \
  'test -n "$RAPIDAPI_KEY" && echo "RAPIDAPI_KEY is set" || echo "RAPIDAPI_KEY is missing"'
```

## 4. Run a low-cost test

Stop Beat and make one page request for each of the seven role queries:

```bash
docker compose stop beat
docker compose exec worker celery -A app.workers.celery_app inspect active
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["jsearch",1]'
docker compose logs -f worker
```

This normally costs about seven requests, plus retries if the provider returns a temporary error.

## 5. Check request usage

```bash
docker compose exec worker python -m app.scripts.jsearch_quota
```

Important fields:

```text
local_used
local_remaining
provider_remaining
application_budget
estimated_scheduled_requests_31_days
```

With defaults:

```text
planned scheduled requests: 2,170/month
hard JobLens stop:           9,000 attempts/month
provider plan:              10,000 requests/month
reserved buffer:             1,000 requests
```

Use a dedicated RapidAPI key for JobLens. Requests made through RapidAPI's browser tester or another application still reduce the provider quota.

## 6. Run the full collection

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["jsearch"]'
```

The generic source is preferred. Do not enable `jsearch,linkedin,indeed` together; that repeats searches and consumes unnecessary quota. Targeted source tasks remain available for deliberate diagnostics but share the same monthly counter and provider lock.

## 7. Inspect publishers and links

Primary source counts:

```bash
docker compose exec postgres psql -U joblens -d joblens -c "
SELECT collection_provider, source, COUNT(*)
FROM job_postings
GROUP BY collection_provider, source
ORDER BY COUNT(*) DESC;"
```

Every apply link:

```bash
docker compose exec postgres psql -U joblens -d joblens -c "
SELECT source, publisher_name, is_direct, COUNT(*)
FROM job_source_sightings
GROUP BY source, publisher_name, is_direct
ORDER BY COUNT(*) DESC;"
```

Confirm JSearch did not retain Simplify:

```bash
docker compose exec postgres psql -U joblens -d joblens -c "
SELECT COUNT(*) AS simplify_links_collected_through_jsearch
FROM job_source_sightings
WHERE collection_provider = 'jsearch'
  AND (source ILIKE '%simplify%' OR source_url ILIKE '%simplify.jobs%');"
```

Expected after the updated scraper is used:

```text
0
```

## 8. Build canonical groups and hiring scores

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.analyze_hiring_activity --args='[1000]'
```

Continue scoring until `remaining_unscored` is zero:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.score_all_jobs --args='[1000, false]'
```

Open:

```text
http://localhost:3000
```

Collapsed cards show all associated application sources under **Found on**.

## 9. Start daily scheduling

```bash
docker compose start beat
```

Simplify runs from its independent public feed. Generic JSearch runs daily with cursor pagination. Identity analysis and scoring run on their separate schedules.

## Capacity estimate

At roughly ten result rows per page:

- one-page test: about 7 requests and up to about 70 returned rows;
- full daily run: 70 requests and up to about 700 returned rows;
- default 31-day schedule: 2,170 requests and up to about 21,700 returned rows;
- protected application ceiling: 9,000 requests and up to about 90,000 returned rows.

These are theoretical returned rows, not guaranteed unique openings. Existing records become updates, pages can be short, queries overlap, and several publishers can carry the same canonical job.
