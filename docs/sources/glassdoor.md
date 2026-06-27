# Glassdoor — Integration Guide

**Status:** ✅ Implemented (`scrapers/glassdoor.py`)

## Unique Value
Glassdoor's primary value beyond job listings is **company ratings and salary data**.
Even if you use another source for job listings, use Glassdoor's company rating
endpoint to enrich the `companies.glassdoor_rating` field.

## Method
RapidAPI Glassdoor endpoint (`glassdoor.p.rapidapi.com`).

## Keys Required
- `RAPIDAPI_KEY`

## Additional: Company Rating Enrichment
```
GET https://glassdoor.p.rapidapi.com/employers/search?keyword={company_name}
```
Returns: rating, review count, CEO approval, salary data.
Schedule this enrichment weekly via a separate Celery task.
