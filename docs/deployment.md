# Deployment

1. Copy `backend/.env.example` to `backend/.env` only when a private environment file does not already exist.
2. Put the rotated RapidAPI marketplace key in `backend/.env` as `RAPIDAPI_KEY=...`.
3. Never place credentials in `.env.example`, Dockerfiles, Compose YAML, screenshots, commits, or GitHub.
4. Use a dedicated RapidAPI application/key for JobLens so outside requests cannot silently consume its quota.
5. Prefer `ENABLED_SCRAPER_SOURCES=simplify,jsearch`; do not also schedule `linkedin` and `indeed` unless duplicate searches are intentional.
6. Keep `JSEARCH_PAGES_PER_QUERY=10`, `JSEARCH_SCHEDULE_EVERY_HOURS=24`, `JSEARCH_MONTHLY_REQUEST_LIMIT=10000`, and `JSEARCH_REQUEST_RESERVE=1000` for the recommended Pro deployment.
7. Build and start with `docker compose up -d --build`.
8. Confirm `alembic current` reports `0006_source_sighting_links`.
9. Confirm the key is present without printing it and inspect quota state with `python -m app.scripts.jsearch_quota` inside the worker.
10. Keep geocoding and embeddings disabled until their quotas, caches, and storage are planned.
11. In production, run migrations as a separate deployment step, remove bind mounts and Uvicorn `--reload`, terminate TLS at a reverse proxy, and use managed PostgreSQL/Redis backups.

The backend development container automatically runs `alembic upgrade head`. Production deployments should avoid having multiple replicas race to run migrations.

Redis stores quota counters on the `redis_data` volume with append-only persistence. Do not use `docker compose down -v` unless deleting both PostgreSQL and Redis state is intentional.
