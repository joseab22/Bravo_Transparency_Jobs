# Validation

Validated for this audited release:

- Python compilation for application and migration files.
- 36 focused backend tests covering title decomposition, identity fingerprints, location handling, original/parallel/repost classification, scraper registry, no-geocoding parser policy, stable-ID creation and update behavior, model-free default title matching, and ORM/migration columns.
- SQLAlchemy mapper configuration: 10 tables, 56 `job_postings` columns, and 16 `location_cache` columns.
- Celery import: eight JobLens tasks and enabled-source-only scheduling.
- Alembic offline PostgreSQL SQL generation through `0003_location_cache`.
- FastAPI health endpoint and route import.
- Frontend TypeScript check.
- Frontend ESLint with zero warnings.
- Next.js production build.
- Production frontend dependency audit with no reported vulnerabilities.
- JSON/YAML parsing, required-file checks, and secret/local-artifact scanning before packaging.

Docker runtime could not be executed inside the editing sandbox. The local next step is `docker compose up -d --build`, followed by the commands in the README.
