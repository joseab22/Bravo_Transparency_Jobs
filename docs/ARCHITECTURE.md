# JobLens Architecture

1. Celery Beat schedules source collection and analysis tasks.
2. Celery workers call JSearch/OpenWeb Ninja and Simplify adapters.
3. Normalized records are idempotently ingested into PostgreSQL with source sightings.
4. Repost detection groups related listings into original, parallel, and repost histories.
5. Scoring calculates ghost-job probability and Active Hiring Confidence.
6. FastAPI exposes validated filtering, sorting, and pagination endpoints.
7. Next.js calls FastAPI through a same-origin `/api` rewrite and renders paginated results.
8. Redis provides the Celery broker, task result backend, scraper locks, and request-budget counters.

Production runs migrations once before starting backend, worker, and Beat. PostgreSQL and Redis remain private; only the frontend should need a public route when the Next.js rewrite is used.
