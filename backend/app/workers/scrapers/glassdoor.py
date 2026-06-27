"""
Glassdoor scraper adapter.

Integration options:

OPTION A — RapidAPI Glassdoor API:
  https://rapidapi.com/Pat92/api/glassdoor
  Env vars: RAPIDAPI_KEY (same key as Indeed/LinkedIn)
  Endpoint: https://glassdoor.p.rapidapi.com/jobs/search

OPTION B — Glassdoor Partner API (requires partnership approval):
  https://www.glassdoor.com/developer/
  Provides company ratings, reviews, and salary data in addition to jobs.
  Env vars: GLASSDOOR_PARTNER_ID, GLASSDOOR_PARTNER_KEY

NOTE: Glassdoor's value-add over other sources is company ratings + salary data.
Even if job scraping uses Option A, use Glassdoor's company rating endpoint
to enrich the Company table with glassdoor_rating.
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

GLASSDOOR_RAPIDAPI_HOST = "glassdoor.p.rapidapi.com"
RAPIDAPI_HEADERS = {
    "X-RapidAPI-Key": settings.rapidapi_key,
    "X-RapidAPI-Host": GLASSDOOR_RAPIDAPI_HOST,
}


class GlassdoorScraper(BaseScraperAdapter):
    source_name = "glassdoor"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or settings.max_pages_per_source)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        """
        Fetch via RapidAPI Glassdoor endpoint.
        Falls back gracefully with empty list if key not configured.
        """
        if not settings.rapidapi_key:
            log.warning("glassdoor_no_api_key", hint="Set RAPIDAPI_KEY in .env")
            return {"jobs": []}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{GLASSDOOR_RAPIDAPI_HOST}/jobs/search",
                headers=RAPIDAPI_HEADERS,
                params={
                    "keyword": query,
                    "page": str(page),
                    "pageSize": "30",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def extract_job_list(self, raw_response) -> list:
        if isinstance(raw_response, dict):
            return raw_response.get("jobs", raw_response.get("data", []))
        return []

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = raw.get("jobTitleText") or raw.get("title", "")
            company_name = raw.get("employerName") or raw.get("company", {}).get("name", "")
            if not title_raw or not company_name:
                return None

            location_raw = raw.get("location", raw.get("locationName", ""))
            title_normalized = normalize_title(title_raw)
            seniority = extract_seniority(title_raw)
            geo = geocode_location(location_raw) if location_raw else None
            metro = geo[2] if geo else normalize_location_text(location_raw)
            description = raw.get("jobDescription", raw.get("description", ""))
            skills = extract_skills(description)
            identity_key = build_job_identity_key(company_name, title_normalized, metro)

            return {
                "source": self.source_name,
                "external_id": str(raw.get("jobListingId") or raw.get("id", "")),
                "source_url": raw.get("jobViewUrl") or raw.get("applyUrl"),
                "company_name": company_name,
                "title_raw": title_raw,
                "title_normalized": title_normalized,
                "seniority": seniority,
                "location_raw": location_raw,
                "city": None,
                "state": None,
                "country": "US",
                "metro_area": metro,
                "latitude": geo[0] if geo else None,
                "longitude": geo[1] if geo else None,
                "remote_type": "Remote" if raw.get("isRemote") else "Onsite",
                "salary_min": raw.get("payPeriodAdjustedPay", {}).get("p10") if isinstance(raw.get("payPeriodAdjustedPay"), dict) else None,
                "salary_max": raw.get("payPeriodAdjustedPay", {}).get("p90") if isinstance(raw.get("payPeriodAdjustedPay"), dict) else None,
                "salary_listed": bool(raw.get("payPeriodAdjustedPay")),
                "employment_type": "Full-time",
                "description_raw": description,
                "skills": skills,
                "date_posted": None,
                "job_identity_key": identity_key,
            }
        except Exception as e:
            log.error("glassdoor_parse_error", error=str(e))
            return None


async def scrape_glassdoor(max_pages: int = None) -> list[dict]:
    scraper = GlassdoorScraper(max_pages)
    return await scraper.scrape()
