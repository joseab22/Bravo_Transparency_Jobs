# JSearch Pro Collection

The generic `jsearch` adapter is the recommended mode. It searches multiple roles once and attributes each returned result to its actual publisher, avoiding separate quota-consuming runs for LinkedIn, Indeed, ZipRecruiter, Glassdoor, Dice, and other publishers.

## Credentials

Put the OpenWeb Ninja API key only in:

```text
backend/.env
```

```env
OPENWEBNINJA_API_KEY=your_openwebninja_key_here
```

## Recommended Pro configuration

```env
ENABLED_SCRAPER_SOURCES=simplify,jsearch
JSEARCH_PAGES_PER_QUERY=10
JSEARCH_SCHEDULE_EVERY_HOURS=24
JSEARCH_MONTHLY_REQUEST_LIMIT=10000
JSEARCH_REQUEST_RESERVE=1400
JSEARCH_QUERIES=software engineer,data analyst,data engineer,data scientist,machine learning engineer,product manager,security engineer
JSEARCH_COUNTRY=us
JSEARCH_LANGUAGE=en
JSEARCH_LOCATION=United States
JSEARCH_DATE_POSTED=month
JSEARCH_EXCLUDED_PUBLISHERS=simplify,simplifyjobs,simplify jobs
JSEARCH_EXCLUDED_DOMAINS=simplify.jobs
ALLOW_OVERLAPPING_JSEARCH_SOURCES=false
```


## Pagination

The adapter uses `/search-v2` and passes the response cursor into the next request. This is the provider-recommended method for fetching more than the first page. One cursor page equals one counted request attempt.

## Simplify exclusion

Simplify is collected independently from its public feeds. JSearch queries append:

```text
-site:simplify.jobs
```

The parser also rejects publishers matching `JSEARCH_EXCLUDED_PUBLISHERS` or URLs matching `JSEARCH_EXCLUDED_DOMAINS`. If a result contains Simplify plus another publisher, only the non-Simplify links are retained. A Simplify-only JSearch result is discarded.

This avoids redundant result slots, although the HTTP search request itself still counts once.

## Extracted fields

The parser maps available response data into JobLens fields:

- provider `job_id`;
- `job_publisher`, primary apply link, and all `apply_options` links;
- direct-application status;
- employer name and website;
- title, normalized role, seniority, and specialization;
- location, city, state, country, coordinates, and remote status;
- listed salary range, currency, and salary period annualization;
- employment type;
- required education and experience;
- occupational categories, department, and employer industry/type;
- description, extracted skills, and posting time.

Missing provider fields remain null rather than being invented.

## Source identity

A JSearch row stores:

```text
collection_provider = jsearch
source              = actual publisher key
publisher_name      = returned publisher label
```

Every distinct normalized application URL is stored in `job_source_sightings`. Tracking parameters are removed so cosmetic URL variants do not create false source entries. Different valid URLs from the same publisher remain separate.

## Manual test

A low-cost one-page test:

```bash
docker compose stop beat
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["jsearch",1]'
```

A full configured run:

```bash
docker compose exec worker celery -A app.workers.celery_app call \
  joblens.scrape_source --args='["jsearch"]'
```

Quota status:

```bash
docker compose exec worker python -m app.scripts.jsearch_quota
```
