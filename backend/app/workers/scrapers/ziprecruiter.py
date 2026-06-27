"""
ZipRecruiter scraper adapter.

Integration options:

OPTION A — ZipRecruiter Publisher API (recommended):
  Free for registered publishers.
  https://www.ziprecruiter.com/publishers
  Endpoint: https://api.ziprecruiter.com/jobs/v1
  Env vars: ZIPRECRUITER_API_KEY

OPTION B — RapidAPI ZipRecruiter endpoint:
  https://rapidapi.com/search/ziprecruiter
  Env vars: RAPIDAPI_KEY

NOTE: ZipRecruiter's Publisher API is one of the most straightforward job APIs.
It returns structured JSON with salary, location, and applicant-friendly fields.
Apply at ziprecruiter.com/publishers for a free API key.
"""

import asyncio
from datetime import datetime
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

from app.core.config import settings
from app.services.normalizer import (
    normalize_title, extract_seniority, geocode_location,
    extract_skills, build_job_identity_key, normalize_location_text,
)
from app.workers.scrapers.base import BaseScraperAdapter

log = structlog.get_logger()

ZR_API_BASE = "https://api.ziprecruiter.com/jobs/v1"


class ZipRecruiterScraper(BaseScraperAdapter):
    source_name = "ziprecruiter"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or settings.max_pages_per_source)
        self.api_key = getattr(settings, "ziprecruiter_api_key", "")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        if not self.api_key:
            log.warning("ziprecruiter_no_api_key", hint="Set ZIPRECRUITER_API_KEY in .env")
            return {"jobs": []}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                ZR_API_BASE,
                params={
                    "search": query,
                    "location": "United States",
                    "radius_miles": 25,
                    "days_ago": 7,
                    "page": page,
                    "jobs_per_page": 20,
                    "api_key": self.api_key,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def extract_job_list(self, raw_response) -> list:
        if isinstance(raw_response, dict):
            return raw_response.get("jobs", [])
        return []

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = raw.get("name", "")
            company_name = raw.get("hiring_company", {}).get("name", "")
            if not title_raw or not company_name:
                return None

            location_raw = raw.get("location", "")
            city = raw.get("city")
            state = raw.get("state")
            title_normalized = normalize_title(title_raw)
            seniority = extract_seniority(title_raw)
            geo = geocode_location(location_raw) if location_raw else None
            metro = geo[2] if geo else normalize_location_text(location_raw)
            description = raw.get("snippet", raw.get("description", ""))
            skills = extract_skills(description)
            identity_key = build_job_identity_key(company_name, title_normalized, metro)

            date_str = raw.get("posted_time")
            date_posted = datetime.fromisoformat(date_str) if date_str else None

            return {
                "source": self.source_name,
                "external_id": str(raw.get("id", "")),
                "source_url": raw.get("job_url") or raw.get("url"),
                "company_name": company_name,
                "title_raw": title_raw,
                "title_normalized": title_normalized,
                "seniority": seniority,
                "location_raw": location_raw,
                "city": city,
                "state": state,
                "country": "US",
                "metro_area": metro,
                "latitude": geo[0] if geo else None,
                "longitude": geo[1] if geo else None,
                "remote_type": "Remote" if raw.get("remote_work_allowed") else "Onsite",
                "salary_min": raw.get("salary_min"),
                "salary_max": raw.get("salary_max"),
                "salary_listed": bool(raw.get("salary_min")),
                "employment_type": "Full-time",
                "description_raw": description,
                "skills": skills,
                "date_posted": date_posted,
                "job_identity_key": identity_key,
            }
        except Exception as e:
            log.error("ziprecruiter_parse_error", error=str(e))
            return None


async def scrape_ziprecruiter(max_pages: int = None) -> list[dict]:
    scraper = ZipRecruiterScraper(max_pages)
    return await scraper.scrape()
