"""Monster-labelled listings via the configured RapidAPI adapter.

No separate MONSTER_API_KEY is consumed by this implementation. Enable only
after validating the endpoint contract and quota for your RapidAPI account.
"""

import asyncio
from datetime import datetime
from typing import Optional
import structlog

from app.core.config import settings
from app.services.normalizer import (
    normalize_title, extract_seniority,
    extract_skills, build_job_identity_key, normalize_location_text,
)
from app.workers.scrapers.base import BaseScraperAdapter

log = structlog.get_logger()

MONSTER_RAPIDAPI_HOST = "monster-job-search.p.rapidapi.com"


class MonsterScraper(BaseScraperAdapter):
    source_name = "monster"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or settings.max_pages_per_source)

    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        if not settings.rapidapi_key:
            log.warning("monster_no_api_key", hint="Set RAPIDAPI_KEY in .env")
            return {"jobResults": []}

        return await self.request_json(
            f"https://{MONSTER_RAPIDAPI_HOST}/jobs/search",
            headers={
                "X-RapidAPI-Key": settings.rapidapi_key,
                "X-RapidAPI-Host": MONSTER_RAPIDAPI_HOST,
            },
            params={
                "q": query,
                "where": "United States",
                "page": page,
                "size": 20,
                "sort": "date",
            },
        )

    def extract_job_list(self, raw_response) -> list:
        if isinstance(raw_response, dict):
            return raw_response.get("jobResults", raw_response.get("jobs", []))
        return []

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = raw.get("title", raw.get("jobTitle", ""))
            company_name = raw.get("company", raw.get("companyName", ""))
            if not title_raw or not company_name:
                return None

            location_raw = raw.get("location", raw.get("jobLocation", {}).get("city", ""))
            title_normalized = normalize_title(title_raw)
            seniority = extract_seniority(title_raw)
            geo = None
            metro = normalize_location_text(location_raw)
            description = raw.get("snippet", raw.get("description", ""))
            skills = extract_skills(description)
            identity_key = build_job_identity_key(company_name, title_normalized, metro)

            return {
                "source": self.source_name,
                "external_id": str(raw.get("id", raw.get("jobId", ""))),
                "source_url": raw.get("applyUrl") or raw.get("jobUrl"),
                "company_name": company_name,
                "title_raw": title_raw,
                "title_normalized": title_normalized,
                "seniority": seniority,
                "location_raw": location_raw,
                "city": raw.get("jobLocation", {}).get("city") if isinstance(raw.get("jobLocation"), dict) else None,
                "state": raw.get("jobLocation", {}).get("state") if isinstance(raw.get("jobLocation"), dict) else None,
                "country": "US",
                "metro_area": metro,
                "latitude": geo[0] if geo else None,
                "longitude": geo[1] if geo else None,
                "remote_type": "Remote" if raw.get("isRemote") else "Onsite",
                "salary_min": None,
                "salary_max": None,
                "salary_listed": False,
                "employment_type": "Full-time",
                "description_raw": description,
                "skills": skills,
                "date_posted": None,
                "job_identity_key": identity_key,
            }
        except Exception as e:
            log.error("monster_parse_error", error=str(e))
            return None


async def scrape_monster(max_pages: int = None) -> list[dict]:
    scraper = MonsterScraper(max_pages)
    return await scraper.scrape()
