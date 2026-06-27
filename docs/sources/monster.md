# Monster — Integration Guide

**Status:** ✅ Implemented (`scrapers/monster.py`)

## Method
RapidAPI Monster Jobs endpoint (`monster-job-search.p.rapidapi.com`).

## Keys Required
- `RAPIDAPI_KEY` (same key as Indeed and Glassdoor)

## Data Available
Title, company, location, description snippet, apply URL.
Monster has less salary data than ZipRecruiter or Indeed.

## Notes
Monster's primary value is coverage depth for mid-career and operations roles.
Lower signal quality than LinkedIn/Indeed for tech roles.
