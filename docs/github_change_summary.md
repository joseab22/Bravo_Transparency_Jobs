# GitHub Change Summary

## Commit title

`fix: harden collection and hiring-activity analysis`

## Summary

Separates scraping from expensive enrichment, prevents duplicate and rate-limited request storms, preserves parallel listings, and makes large-feed identity and scoring runs safer.

## Important changes

- Removes per-posting geocoding and model generation from ingestion.
- Adds cached, opt-in unique-location enrichment with Nominatim or Google support.
- Adds shared HTTP backoff and Redis per-source task locks.
- Prefetches companies and stable source IDs before batched ingestion.
- Preserves simultaneous source listings and classifies original, parallel, and repost history afterward.
- Bounds candidate comparisons and keeps semantic title matching opt-in.
- Invalidates stale scores whenever identity or enriched location data changes.
- Aligns ORM models, migrations, API schemas, frontend types, Docker, CI, tests, and documentation.
