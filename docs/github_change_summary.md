# GitHub change summary

## Commit title

`feat: add structured tech-job identity and active hiring confidence`

## Summary

Adds tech-focused title decomposition, distinguishes parallel openings from true reposts, and introduces an Active Hiring Confidence score.

## Description

- Decomposes titles into job family, seniority, and specializations.
- Keeps roles such as `Senior Software Engineer - Admin` and `Senior Software Engineer - Lead` distinct.
- Rebuilds identity keys centrally during ingestion instead of trusting source-specific keys.
- Stores different external IDs as separate observations rather than overwriting simultaneous openings.
- Classifies listings as original, parallel, or repost using stable source IDs, timing, active state, role structure, and location behavior.
- Treats remote listings across regions and simultaneous multi-location listings as parallel rather than reposted.
- Requires a previously inactive listing and a configurable gap before creating a repost chain.
- Uses title embeddings for uncertain taxonomy matches and stored description embeddings to reject unrelated under-specified roles.
- Adds `active_hiring_confidence` to the database, API, scoring pipeline, and frontend.
- Adds migration `0002_structured_identity.py`, expanded unit tests, and identity-resolution documentation.
- Fixes the invalid Jobright Celery schedule and adds a non-interactive Next.js ESLint configuration for CI.
