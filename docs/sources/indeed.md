# Indeed — Integration Guide

**Status:** ✅ Implemented (`scrapers/indeed.py`)

## Method
JSearch API via RapidAPI — returns structured JSON covering Indeed listings.

## Keys Required
- `RAPIDAPI_KEY` — sign up at https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch

## Rate Limits
| Tier | Requests/month | Cost |
|------|---------------|------|
| Free | 100 | $0 |
| Basic | 500 | ~$10 |
| Pro | 10,000 | ~$50 |

## Data Available
Job title, company, location, salary (when listed), employment type, remote type, description, date posted.

## Activation
Set `RAPIDAPI_KEY` in `.env`. The scraper runs automatically every 6h via Celery beat.
