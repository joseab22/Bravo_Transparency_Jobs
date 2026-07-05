# Dependency Map

```text
scrapers/base.py
  └─ source adapters
       └─ services/normalizer.py (pure parsing only)
            └─ workers/ingestion.py
                 └─ PostgreSQL models/migrations

services/location_enrichment.py ── location_cache + job_postings
services/embedding_enrichment.py ─ job_embeddings
services/repost_detector.py ────── structured history classification
services/scoring.py ────────────── Active Hiring Confidence
workers/celery_app.py ──────────── orchestration and scheduling
api/routes + schemas ───────────── frontend/src/lib + types
```
