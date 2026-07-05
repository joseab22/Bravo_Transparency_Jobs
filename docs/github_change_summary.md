# GitHub change summary

## Commit title

`feat: add structured job identity and resilient scraper execution`

## Summary

Adds tech-focused job identity resolution, Active Hiring Confidence, and safer scraper execution with shared rate-limit handling and duplicate-task prevention.

## Description

- Decomposes job titles into family, seniority, and specialization.
- Distinguishes original listings, parallel openings, and true reposts.
- Handles remote and simultaneous multi-location postings without inflating repost counts.
- Adds structured identity fields and Active Hiring Confidence across the database, API, scoring pipeline, and frontend types.
- Adds shared HTTP `429`, `Retry-After`, exponential-backoff, jitter, network, and temporary `5xx` handling across all scrapers.
- Prevents overlapping scrapes of the same source with Redis locks and safer Celery task settings.
- Includes migration `0002_structured_identity.py`, updated documentation, frontend ESLint configuration, and scraper schedule fixes.
