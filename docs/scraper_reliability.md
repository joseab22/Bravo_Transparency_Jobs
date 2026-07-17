# Scraper Reliability

## Shared request controls

Every HTTP adapter uses the common base client, which provides:

- one reusable client per scraper run;
- `429` and `Retry-After` handling;
- exponential backoff with jitter;
- retries for temporary `5xx`, timeout, and network errors;
- delays between result pages;
- per-run duplicate merging and optional record caps.

## Duplicate-task prevention

Celery uses Redis locks. Ordinary sources use one lock per source. Generic JSearch and its optional LinkedIn/Indeed targeted variants share the `jsearch-provider` lock so they cannot run concurrently and violate the provider rate limit. Worker prefetch is `1` and local concurrency defaults to `1`.

## JSearch request-budget enforcement

Every JSearch request attempt is reserved in Redis before transmission. This includes retries.

Default Pro controls:

```text
monthly provider limit: 10,000
JobLens local ceiling:   9,000
reserved buffer:         1,000
planned daily schedule:  2,170 requests per 31 days
```

The budget service also records the provider's request-limit, remaining, and reset headers. Collection stops when provider-reported remaining requests reach the reserve, even when local usage is lower. Redis append-only persistence protects the counter across normal restarts.

Configuration validation rejects a scheduled plan that exceeds the protected local budget and rejects simultaneous generic plus targeted JSearch scheduling unless `ALLOW_OVERLAPPING_JSEARCH_SOURCES=true`.

Check status with:

```bash
docker compose exec worker python -m app.scripts.jsearch_quota
```

A dedicated OpenWeb Ninja key is recommended because requests made outside JobLens consume the same provider quota.

## JSearch pagination and attribution

The adapter uses cursor-based `/search-v2` pagination. One cursor page is one request. It stores `collection_provider=jsearch` separately from the returned publisher, and preserves every distinct normalized apply URL.

Simplify is excluded at both query and parser levels because JobLens already collects Simplify from its keyless public feeds. The exclusion prevents redundant result slots but cannot make an already-sent JSearch HTTP request free.

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

A source task may ingest partial results after an upstream rate limit or after the protected budget stops a run. A single failed or partial run therefore does not immediately mark absent listings inactive. The optional stale-job task uses a conservative window and is disabled by default during initial testing.

A returned row count is not a unique-job count. Query overlap, repeated daily observations, and several publishers can all refer to the same canonical opening.
