# Scraper Reliability

JobLens centralizes HTTP safety in `backend/app/workers/scrapers/base.py`.

## Shared request behavior

Every HTTP-based adapter uses `request_json()` for:

- HTTP `429` handling
- `Retry-After` support
- exponential backoff with random jitter
- retries for temporary `408`, `425`, and `5xx` responses
- retries for timeouts and transient network failures
- courtesy delays between pages and queries

Persistent rate limiting stops the current source cleanly rather than immediately requesting every remaining page.

## Duplicate-task prevention

`joblens.scrape_source` obtains a Redis lock named for the source. Only one task per source can run at a time. Different sources may still run independently.

Celery is configured with reduced prefetching and late acknowledgments. Local Docker testing uses worker concurrency `1` to minimize accidental overlap while the integrations are being validated.

## Local verification

```bash
docker compose stop beat
docker compose exec worker celery -A app.workers.celery_app purge -f
docker compose up -d --build backend worker

docker compose exec worker celery -A app.workers.celery_app inspect active
docker compose exec worker celery -A app.workers.celery_app inspect reserved
```

Trigger one source once:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["simplify"]'
```

Inspect results:

```bash
docker compose logs -f worker

docker compose exec postgres psql -U joblens -d joblens \
  -c "SELECT source, COUNT(*) FROM job_postings GROUP BY source;"
```

A backoff policy respects an upstream limit; it does not bypass provider quotas or access restrictions.
