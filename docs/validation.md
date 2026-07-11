# Validation

Validated for this release:

- Python compilation for application, migration, script, and test files.
- 53 backend tests covering title decomposition, identity fingerprints, location handling, original/parallel/repost classification, stable-ID ingestion, JSearch structured extraction, Simplify exclusion, cursor pagination, multi-link publisher attribution, canonical source aggregation, request-budget stopping, and legacy fallback.
- SQLAlchemy mapper configuration.
- Celery task and enabled-source scheduling imports.
- Alembic offline PostgreSQL SQL generation through `0006_source_sighting_links`.
- FastAPI route/schema imports.
- Frontend TypeScript check.
- Frontend ESLint with zero warnings.
- Next.js production build.
- Frontend production dependency audit with zero reported vulnerabilities.
- Archive secret/local-artifact scan.

Docker runtime should be verified locally with `docker compose up -d --build`, followed by the commands in the README.
