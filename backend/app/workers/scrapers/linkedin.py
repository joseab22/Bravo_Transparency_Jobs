"""
LinkedIn scraper adapter.

Integration options (choose one based on access level):

OPTION A — RapidAPI JSearch (covers LinkedIn results, easiest):
  Same RAPIDAPI_KEY used for Indeed. Query with "site:linkedin.com" suffix.
  Endpoint: https://jsearch.p.rapidapi.com/search

OPTION B — LinkedIn Jobs API (requires LinkedIn partner approval):
  https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/
  Requires OAuth 2.0 via LinkedIn developer app.
  Env vars: LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET

OPTION C — Playwright browser scraping (no API key, higher maintenance):
  Automates https://www.linkedin.com/jobs/search/
  Requires Playwright + authenticated session cookie.
  Env vars: LINKEDIN_SESSION_COOKIE

NOTE: LinkedIn actively blocks automated scraping. Option A (JSearch) is the
most reliable production path. Option C requires rotating proxies at scale.

Set LINKEDIN_SCRAPER_MODE in .env to: "jsearch" | "api" | "playwright"
"""

import asyncio
from datetime import datetime
from typing import Optional
import structlog

from app.core.config import settings
from app.services.normalizer import (
    normalize_title, extract_seniority, geocode_location,
    extract_skills, build_job_identity_key, normalize_location_text,
)
from app.workers.scrapers.base import BaseScraperAdapter

log = structlog.get_logger()

JSEARCH_BASE = "https://jsearch.p.rapidapi.com"
RAPIDAPI_HEADERS = {
    "X-RapidAPI-Key": settings.rapidapi_key,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}


class LinkedInScraper(BaseScraperAdapter):
    source_name = "linkedin"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or settings.max_pages_per_source)
        self.mode = getattr(settings, "linkedin_scraper_mode", "jsearch")

    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        if self.mode == "jsearch":
            return await self._fetch_jsearch(query, page)
        raise NotImplementedError(
            f"LinkedIn scraper mode '{self.mode}' not yet implemented. "
            "Set LINKEDIN_SCRAPER_MODE=jsearch in .env."
        )

    async def _fetch_jsearch(self, query: str, page: int) -> dict:
        if not settings.rapidapi_key:
            log.warning("linkedin_no_api_key", hint="Set RAPIDAPI_KEY in .env")
            return {"data": []}

        return await self.request_json(
            f"{JSEARCH_BASE}/search",
            headers=RAPIDAPI_HEADERS,
            params={
                "query": f"{query} site:linkedin.com",
                "page": str(page),
                "num_pages": "1",
                "date_posted": "week",
            },
        )

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = raw.get("job_title", "")
            company_name = raw.get("employer_name", "")
            if not title_raw or not company_name:
                return None

            location_raw = f"{raw.get('job_city', '')}, {raw.get('job_state', '')}".strip(", ")
            title_normalized = normalize_title(title_raw)
            seniority = extract_seniority(title_raw)
            geo = geocode_location(location_raw) if location_raw else None

            sal_min, sal_max = self._normalize_salary(raw)
            description = raw.get("job_description", "")
            skills = extract_skills(description)
            metro = geo[2] if geo else normalize_location_text(location_raw)
            identity_key = build_job_identity_key(company_name, title_normalized, metro)

            date_str = raw.get("job_posted_at_datetime_utc")
            date_posted = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else None

            return {
                "source": self.source_name,
                "external_id": raw.get("job_id"),
                "source_url": raw.get("job_apply_link") or raw.get("job_google_link"),
                "company_name": company_name,
                "title_raw": title_raw,
                "title_normalized": title_normalized,
                "seniority": seniority,
                "location_raw": location_raw,
                "city": raw.get("job_city"),
                "state": raw.get("job_state"),
                "country": raw.get("job_country", "US"),
                "metro_area": metro,
                "latitude": geo[0] if geo else None,
                "longitude": geo[1] if geo else None,
                "remote_type": "Remote" if raw.get("job_is_remote") else "Onsite",
                "salary_min": sal_min,
                "salary_max": sal_max,
                "salary_listed": bool(sal_min),
                "employment_type": self._map_employment(raw.get("job_employment_type")),
                "description_raw": description,
                "skills": skills,
                "date_posted": date_posted,
                "job_identity_key": identity_key,
            }
        except Exception as e:
            log.error("linkedin_parse_error", error=str(e))
            return None

    def _normalize_salary(self, raw: dict):
        sal_min = raw.get("job_min_salary")
        sal_max = raw.get("job_max_salary")
        period = raw.get("job_salary_period", "")
        if period == "HOUR" and sal_min:
            sal_min, sal_max = int(sal_min * 2080), int(sal_max * 2080) if sal_max else None
        elif period == "MONTH" and sal_min:
            sal_min, sal_max = int(sal_min * 12), int(sal_max * 12) if sal_max else None
        return (int(sal_min) if sal_min else None), (int(sal_max) if sal_max else None)

    def _map_employment(self, raw: Optional[str]) -> str:
        if not raw:
            return "Full-time"
        raw = raw.upper()
        if "PART" in raw: return "Part-time"
        if "CONTRACT" in raw or "TEMP" in raw: return "Contract"
        if "INTERN" in raw: return "Internship"
        return "Full-time"

    async def rate_limit_sleep(self):
        await asyncio.sleep(1.0)  # LinkedIn is stricter


async def scrape_linkedin(max_pages: int = None) -> list[dict]:
    scraper = LinkedInScraper(max_pages)
    return await scraper.scrape()
