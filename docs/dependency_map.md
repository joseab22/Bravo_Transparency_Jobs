# Dependency Map

```text
scrapers/base.py
  ├─ shared HTTP retry/rate-limit/request counting
  ├─ duplicate result merging
  └─ source adapters
       ├─ scrapers/jsearch.py
       │    ├─ /search-v2 cursor pagination
       │    ├─ publisher/apply-option attribution
       │    ├─ Simplify exclusion
       │    └─ services/request_budget.py
       │         ├─ Redis atomic monthly counter
       │         └─ RapidAPI quota-header reconciliation
       └─ services/normalizer.py
            ├─ tracking-safe apply URL normalization
            └─ workers/ingestion.py
                 ├─ provider-ID upsert
                 ├─ many source sightings per posting
                 └─ PostgreSQL models/migrations

services/source_attribution.py ─ canonical-group apply-link aggregation
services/location_enrichment.py ─ location_cache + job_postings
services/embedding_enrichment.py ─ job_embeddings
services/repost_detector.py ────── structured history classification
services/scoring.py ─────────────── Active Hiring Confidence
workers/celery_app.py ───────────── orchestration, shared JSearch lock, daily schedule, quota task
app/scripts/jsearch_quota.py ────── operator quota inspection
api/routes + schemas ────────────── collapse_canonical + canonical_sources
frontend/src/lib + types + pages ── linked Found on publisher display
```
