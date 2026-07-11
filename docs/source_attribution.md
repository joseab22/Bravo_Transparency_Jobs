# Source Attribution and Canonical Display

## Provider versus publisher

JobLens stores two separate concepts:

- `collection_provider`: the service used to obtain a record, such as `jsearch` or `simplify`;
- `source`: the actual publisher carrying an application link, such as `linkedin`, `indeed`, `ziprecruiter`, `glassdoor`, `dice`, `company_site`, or another normalized publisher.

For JSearch, the primary `job_publisher` remains the posting row's primary source. Every distinct publisher/application URL in `apply_options` becomes a `job_source_sightings` row.

## Link identity

Each sighting has a SHA-256 `sighting_key` derived from:

```text
normalized publisher + normalized apply URL + provider external ID
```

Common marketing/tracking query parameters are removed before key generation. Therefore:

- the same link with different UTM/referrer parameters is one sighting;
- different application URLs from the same publisher remain separate;
- an employer's direct careers link can coexist with LinkedIn, Indeed, or other board links.

## Duplicate behavior

1. The same `collection_provider + external_id` is one posting and is updated on later collection.
2. Additional publisher URLs returned for that posting become source sightings.
3. Different external IDs remain separate posting rows during ingestion.
4. Identity analysis may place compatible rows under the same `canonical_job_id` and classify later rows as `parallel` or `repost`.
5. The API collapses canonical groups by default and aggregates sightings across all member rows.
6. The same exact apply URL found under multiple member rows is shown once; different URLs remain accessible.

This preserves provenance without forcing users to browse repeated cards for one opening.

## API behavior

`GET /api/v1/jobs/` accepts:

```text
collapse_canonical=true   # default: one representative card per canonical group
collapse_canonical=false  # every stored posting row
```

`canonical_sources` contains one item per distinct apply link with:

- publisher key and display name;
- collection provider;
- application URL;
- provider external ID;
- direct-employer flag;
- first/last sighting dates;
- active status;
- member listing IDs.

Legacy rows without a sighting record fall back to the posting's primary source.

## Frontend behavior

The homepage requests collapsed results and displays `canonical_sources` as linked **Found on** chips. When one publisher has multiple valid application URLs, labels are numbered. Employer-direct links are marked **Direct**.
