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
## 2026-07-05 — Text-capacity and ingestion recovery

- Added migration `0004_text_capacity` to widen normalized role and metro fields.
- Multi-location postings now keep the complete source text in `location_raw` and use `Multiple locations` as the analysis bucket.
- Location enrichment applies the same field bounds as ingestion.
- Ingestion rebuilds eager-loaded caches after a failed savepoint to prevent secondary `MissingGreenlet` errors.


## 0.4.0 — JSearch publisher attribution and canonical source display

- Separated JSearch collection provider from the actual publisher.
- Preserved `job_publisher` and every `apply_options` publisher/link as source sightings.
- Merged repeated JSearch job IDs collected through different board-specific queries.
- Aggregated sources across canonical groups in list, detail, and company-job APIs.
- Added `collapse_canonical`, enabled by default, while preserving raw-row access.
- Added frontend **Found on** links for every known publisher.
- Added migration `0005_source_attribution` and legacy-source fallback behavior.
- Added a quota-efficient generic mixed-publisher JSearch source, retained targeted LinkedIn/Indeed variants, changed JSearch-backed Beat schedules to weekly, and defaulted page depth to one.
- Added HTTP request counts to scraper completion logs and expanded tests to 43.

## 0.5.0 — JSearch Pro quota and multi-link attribution

- Added migration `0006_source_sighting_links` so one posting can retain several distinct links from the same publisher.
- Added cursor-based JSearch `/search-v2` pagination.
- Added Redis-backed atomic monthly request admission for all JSearch-backed attempts, including retries.
- Added RapidAPI quota-header reconciliation and a protected 1,000-request reserve.
- Added daily Pro defaults: 2,170 planned requests per 31-day month and a hard JobLens stop at 9,000 attempts.
- Added persistent Redis AOF storage for request-budget state.
- Added a shared provider lock across generic JSearch and targeted LinkedIn/Indeed tasks.
- Added startup validation against unsafe schedules and accidental generic/targeted overlap.
- Added query and response filtering to exclude Simplify from JSearch while retaining the direct Simplify feeds.
- Expanded structured response extraction and tracking-safe URL normalization.
- Bounded all scraped company, title, location, website, and classification text to the matching ORM column capacities before ingestion.
- Added a quota-status command and Celery task.
- Numbered repeated publisher links and marked direct employer links in the frontend.
- Expanded backend coverage to 53 tests and updated all operational documentation.
