# Repository Audit Report

## High-impact issues corrected

- Per-record geocoding caused thousands of external requests after successful feed downloads.
- Separate scraper implementations had inconsistent retry and rate-limit behavior.
- Duplicate Celery tasks could scrape the same source concurrently.
- Structured identity migration columns and ORM/API/frontend declarations were inconsistent.
- Distinct same-source listings could be collapsed by broad identity matching.
- Historical classification could run unbounded semantic model work on large feeds.
- Repost-event rebuilding deleted events outside the configured analysis window.
- Large feeds repeated company and stable-ID database lookups for nearly every row.
- JSearch publisher attribution was previously tied to the adapter name rather than the returned publisher.
- One publisher per posting could not represent several application URLs or direct employer links.
- Free-tier scheduling did not provide a durable hard request budget.
- Frontend dependencies and lint/build scripts were outdated or inconsistent.

## Resulting pipeline

```text
rate-limited source collection
→ JSearch request-budget admission
→ provider/publisher/apply-link attribution
→ pure normalization
→ company/stable-ID prefetch
→ batched PostgreSQL ingestion
→ optional cached location/embedding enrichment
→ bounded identity-history classification
→ Active Hiring Confidence scoring
→ canonical API/frontend display
```

## JSearch Pro audit

- Uses generic mixed-publisher JSearch by default, avoiding separate board-filtered runs.
- Uses provider-recommended `/search-v2` cursor pagination.
- Keeps the returned `job_publisher` as the primary row attribution.
- Preserves every distinct `apply_options` URL and direct-company link.
- Separates `collection_provider=jsearch` from the actual publisher.
- Excludes Simplify through query-domain exclusions and response filtering.
- Merges repeated JSearch job IDs found across queries.
- Aggregates application links across canonical job groups.
- Adds Redis atomic request admission for every attempt, including retries.
- Stops at 9,000 local attempts and at the provider's 1,000-request remaining reserve.
- Persists quota state with Redis append-only storage.
- Rejects unsafe scheduled configurations and generic/targeted overlap.
- Defaults to a daily 2,170-request monthly schedule rather than consuming the entire 10,000-request plan.

## Remaining operational realities

- Provider credentials, prices, quotas, contracts, and response schemas can change independently of this repository.
- Requests made outside JobLens with the same RapidAPI key still count. Use a dedicated key.
- A first scrape produces preliminary signals; repeated observations are required for stronger history-based evidence.
- Returned rows are not unique-job counts because queries and publishers overlap.
- Geocoding and embeddings remain optional because they have external quotas and compute/storage costs.
