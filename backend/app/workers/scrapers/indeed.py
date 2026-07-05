"""
Indeed scraper adapter.

Uses the JSearch API via RapidAPI (most reliable programmatic access).
Endpoint: https://jsearch.p.rapidapi.com/search

Keys required: RAPIDAPI_KEY in .env
Sign up: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
Free tier: 100 req/month | Basic: 500/month
"""

import asyncio
from datetime import datetime
from typing import Optional
import structlog

from app.core.config import settings
from app.services.normalizer import (
    normalize_title, extract_seniority, geocode_location,
    normalize_location_text, extract_skills, build_job_identity_key,
)
from app.workers.scrapers.base import BaseScraperAdapter

log = structlog.get_logger()

JSEARCH_BASE = "https://jsearch.p.rapidapi.com"
RAPIDAPI_HEADERS = {
    "X-RapidAPI-Key": settings.rapidapi_key,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}

SEARCH_QUERIES = [
    "data analyst",
    "data engineer",
    "data scientist",
    "machine learning engineer",
    "software engineer",
    "business analyst",
    "analytics engineer",
]


class IndeedScraper(BaseScraperAdapter):
    source_name = "indeed"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or settings.max_pages_per_source)

    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        if not settings.rapidapi_key:
            log.warning("indeed_no_api_key", hint="Set RAPIDAPI_KEY in .env")
            return {"data": []}

        return await self.request_json(
            f"{JSEARCH_BASE}/search",
            headers=RAPIDAPI_HEADERS,
            params={
                "query": query,
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
            metro = geo[2] if geo else normalize_location_text(location_raw)

            sal_min, sal_max = self._normalize_salary(raw)
            description = raw.get("job_description", "")
            skills = extract_skills(description)
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
            log.error("indeed_parse_error", error=str(e))
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

    def default_queries(self) -> list[str]:
        return SEARCH_QUERIES


async def scrape_indeed(max_pages: int = None) -> list[dict]:
    scraper = IndeedScraper(max_pages)
    return await scraper.scrape()
