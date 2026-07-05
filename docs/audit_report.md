# Repository Audit Report

## High-impact issues corrected

- Per-record geocoding caused thousands of external requests after a successful feed download.
- Separate scraper implementations had inconsistent retry and rate-limit behavior.
- Duplicate Celery tasks could scrape the same source concurrently.
- Structured identity migration columns and ORM/API/frontend declarations were inconsistent.
- Distinct same-source listings could be collapsed by broad identity matching.
- Historical classification could run unbounded semantic model work on large feeds.
- Repost-event rebuilding deleted events outside the configured analysis window.
- Large feeds repeated company and stable-ID database lookups for nearly every row.
- An advertised classification switch was a no-op, and ingestion could optionally trigger expensive embedding generation.
- Geocoding excluded rows with a null work arrangement and advertised a Google key without implementing the provider.
- First-observation data confidence was overstated relative to repeated sightings.
- Test database engine configuration assumed PostgreSQL and broke isolated SQLite tests.
- Frontend dependencies and lint/build scripts were outdated or inconsistent.

## Resulting pipeline

```text
rate-limited source collection
→ pure normalization
→ company/stable-ID prefetch
→ batched PostgreSQL ingestion
→ optional cached location/embedding enrichment
→ bounded identity-history classification
→ Active Hiring Confidence scoring
→ API/frontend
```

## Remaining operational realities

- Provider credentials, quotas, contracts, and response schemas can change independently of this repository.
- A first scrape produces preliminary signals; repeated observations are required for stronger history-based evidence.
- Stale-job expiration is conservative and disabled by default until scheduled collection is demonstrated to be reliable.
- Geocoding and embeddings remain optional because they have external quotas and compute/storage costs.
