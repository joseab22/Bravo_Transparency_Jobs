# Structured Job Identity and Repost Classification

JobLens uses a hybrid rules-first approach designed initially for technology jobs.

## Title decomposition

`decompose_title()` converts a raw title into:

- `job_family` — stable role family such as `software engineer` or `data engineer`
- `seniority` — `entry`, `mid`, `senior`, `lead`, or `executive`
- `specialization` — sorted tags such as `backend`, `platform`, `admin`, or `tech_lead`
- `title_parse_confidence` — confidence that the controlled taxonomy recognized the role

Known structured fields are compared before any embedding model is used. This keeps decisions explainable and prevents distinct roles such as `admin` and `tech_lead` from being collapsed.

## Two identity values

`job_identity_key` is human-readable and includes the location bucket for onsite/hybrid work. Remote roles always use the `remote` location bucket.

`identity_fingerprint` is a location-independent SHA-256 value used to find related remote or multi-location listings. Location compatibility is decided by the classifier rather than encoded permanently into this fingerprint.

## Classification rules

The ingestion pipeline first updates an existing row only when it has a stable source match:

1. same source and external ID;
2. otherwise same source URL;
3. otherwise a recent identical source record when the feed has neither.

A newly inserted listing is then compared with earlier listings from the same company:

### Duplicate

Same source and same external ID. The ingestion pipeline normally updates this record in place.

### Parallel

A related title with a different external ID is classified as parallel when:

- it was posted within `PARALLEL_LISTING_WINDOW_DAYS`; or
- an earlier related listing is still active in the same location/remote scope; or
- a closed listing reopens before `REPOST_MIN_GAP_DAYS`.

This includes remote postings advertised in different states and simultaneous multi-location postings. Parallel listings remain separate database observations but share a `canonical_job_id`, allowing them to contribute evidence of active headcount without increasing repost counts.

### Repost

A repost requires all of the following:

- compatible company, role family, specialization, seniority, and employment type;
- compatible remote/location scope;
- the previous related listing is inactive;
- the new listing returns at least `REPOST_MIN_GAP_DAYS` after the previous listing was last seen.

### Original

A listing is original when no prior listing satisfies the parallel or repost rules.

## Semantic fallback

Sentence-transformer title similarity is only used when at least one title has low taxonomy confidence. High-confidence titles with different known families or different non-empty specializations are not overridden by embeddings. When either title lacks a specialization, stored job-description embeddings must also meet `DESCRIPTION_SIMILARITY_THRESHOLD` before the listings can share a parallel or repost chain.

## Active Hiring Confidence

`active_hiring_confidence` is a 0–100 positive-facing score combining:

- inverse ghost-job probability;
- posting freshness;
- activity score;
- applicant trend;
- number of related active listings;
- original/parallel/repost classification.

Parallel active openings provide modest positive evidence. Verified reposts reduce confidence and increase ghost-job probability.

## Scraper and ingestion reliability

Identity resolution depends on receiving stable, non-duplicated observations. All HTTP adapters now use the shared `BaseScraperAdapter.request_json()` path for `429`, `Retry-After`, exponential-backoff, jitter, temporary `5xx`, timeout, and network handling.

Celery also acquires a Redis lock per source before scraping. A second task for the same source is skipped while the first is active. This prevents overlapping fetches from creating avoidable upstream traffic or duplicate ingestion attempts. These protections do not change the original/parallel/repost rules; they make the input stream more reliable.
