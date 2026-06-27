# Dice — Integration Guide

**Status:** ✅ Implemented (`scrapers/dice.py`)

## Method
Dice public Job Search API — no API key required for basic usage.
Endpoint: `https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search`

## Keys Required
None (optional: `DICE_API_KEY` for higher rate limits)

## Data Available
Title, company, location, employment type, work setting (remote/hybrid/onsite),
skills (pre-extracted by Dice), posted date, salary when listed.

## Notes
Dice specializes in tech roles. Their pre-extracted skills field is useful as a
cross-check against our own skill extractor. No key needed — activate by default.
