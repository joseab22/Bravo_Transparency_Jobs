# Scraper Reliability

## Shared request controls

Every HTTP adapter uses the common base client, which provides:

- one reusable client per scraper run;
- `429` and `Retry-After` handling;
- exponential backoff with jitter;
- retries for temporary `5xx`, timeout, and network errors;
- delays between result pages;
- per-run deduplication and optional record caps.

## Duplicate-task prevention

Celery uses a Redis lock per source. A second task for the same source is skipped while the first lock is active. Worker prefetch is `1` and local concurrency defaults to `1`.

## Geocoding

Scraper parsers perform no geocoding. Collection stores normalized location text immediately. The optional `joblens.enrich_locations` task:

1. selects unique uncached location strings;
2. skips remote and multi-location labels;
3. checks `location_cache`;
4. makes rate-limited requests only for missing locations;
5. updates all jobs sharing the same raw location;
6. invalidates affected scores so they can be recalculated.

Nominatim and Google are supported through `GEOCODING_PROVIDER`. Google requires `GOOGLE_GEOCODING_API_KEY`. `GEOCODING_ENABLED=false` is the safe default.

## Large feeds

Before row processing, ingestion normalizes records, resolves each unique company once, and prefetches existing stable IDs and URLs in chunks. It then commits in configurable batches and only writes a new snapshot when mutable data changed or the snapshot interval elapsed.

This allows a large feed to make durable progress without performing model downloads or geocoding in the insert loop.

## Source completeness

A source task may ingest partial results after an upstream rate limit. For that reason, a single failed or partial run does not immediately mark absent listings inactive. The optional stale-job task uses a conservative time window and is disabled by default during initial testing.
