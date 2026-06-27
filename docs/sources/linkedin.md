# LinkedIn — Integration Guide

**Status:** ✅ Implemented (`scrapers/linkedin.py`)

## Methods (choose one)

### Option A — JSearch via RapidAPI (default, easiest)
Same key as Indeed. Set `LINKEDIN_SCRAPER_MODE=jsearch`.

### Option B — LinkedIn Official Jobs API
Requires LinkedIn partner approval (apply at linkedin.com/developers).
Set `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET`.

### Option C — Playwright headless browser
Set `LINKEDIN_SCRAPER_MODE=playwright`.
Requires rotating proxies at scale. LinkedIn actively blocks automated access.

## Keys Required
- Option A: `RAPIDAPI_KEY` only
- Option B: `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`

## Notes
LinkedIn is the highest-volume source. Start with Option A.
Their job listings include applicant counts and "Easy Apply" signals.
