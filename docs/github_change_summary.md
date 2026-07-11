# GitHub Change Summary

## Commit title

`add safe JSearch Pro collection`

## Summary

Adds protected JSearch Pro pagination, accurate publisher/apply-link attribution, Simplify exclusion, and canonical multi-board display.

## Important changes

- Stores `collection_provider` separately from actual publisher `source`.
- Parses `job_publisher`, employer details, job structure, and every JSearch `apply_options` URL.
- Uses `/search-v2` cursor pagination.
- Excludes Simplify domains/publishers from JSearch while continuing direct Simplify collection.
- Merges repeated provider IDs and preserves several URLs from one publisher.
- Aggregates source evidence across canonical job groups.
- Displays linked **Found on** chips, including numbered duplicate-publisher links and **Direct** employer links.
- Adds migration `0006_source_sighting_links`.
- Adds a Redis-backed 9,000-attempt ceiling, 1,000-request reserve, provider-header reconciliation, and persistent quota state.
- Defaults generic JSearch to one daily run: 2,170 planned monthly requests.
- Prevents generic and targeted JSearch schedules from overlapping by default.
- Aligns settings, scrapers, normalization, ingestion, ORM, migrations, API, frontend, tests, Docker, and documentation.
