# Changelog

## 0.3.0 — Collection and analysis audit

- Removed network geocoding and embedding generation from source ingestion.
- Added `location_cache` and opt-in unique-location enrichment with Nominatim or Google.
- Centralized normalization and structured technology-title parsing.
- Corrected ORM/migration type and column mismatches.
- Preserved distinct stable source IDs during ingestion.
- Added company/stable-ID prefetching, batched commits, and snapshot throttling.
- Reworked original/parallel/repost classification, bounded candidate matching, and score invalidation.
- Kept semantic title and description embeddings opt-in.
- Added Active Hiring Confidence analysis tasks and API filters.
- Added enabled-source-only Celery scheduling, source locks, and retry/backoff controls.
- Updated frontend dependencies, CI, Docker images, tests, and documentation.
