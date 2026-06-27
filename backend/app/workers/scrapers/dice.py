"""
Dice scraper adapter.

Dice specializes in tech jobs and has a public REST API.

OPTION A — Dice Jobs API (recommended, no key required for basic search):
  https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search
  No auth required for basic job search. Higher rate limits with API key.
  Env vars: DICE_API_KEY (optional)

OPTION B — RapidAPI Dice endpoint:
  Env vars: RAPIDAPI_KEY

Dice returns clean JSON with skills, employment type, posted date, and
work setting (remote/onsite/hybrid) — well-structured for our pipeline.
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

DICE_API_BASE = "https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search"


class DiceScraper(BaseScraperAdapter):
    source_name = "dice"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or settings.max_pages_per_source)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        headers = {"x-api-key": settings.dice_api_key} if getattr(settings, "dice_api_key", "") else {}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                DICE_API_BASE,
                headers=headers,
                params={
                    "q": query,
                    "countryCode2": "US",
                    "pageSize": 20,
                    "page": page,
                    "facets": "employmentType|postedDate|workplaceTypes",
                    "fields": "id|jobId|title|companyName|location|postalCode|country|"
                              "employmentDetails|workplaceTypes|postedDate|applyDataStatus|"
                              "easyApply|descriptionFragment|taxTerms|salary",
                    "postedDate": "ONE_WEEK",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def extract_job_list(self, raw_response) -> list:
        if isinstance(raw_response, dict):
            return raw_response.get("data", [])
        return []

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = raw.get("title", "")
            company_name = raw.get("companyName", "")
            if not title_raw or not company_name:
                return None

            location_raw = raw.get("location", "")
            title_normalized = normalize_title(title_raw)
            seniority = extract_seniority(title_raw)
            geo = geocode_location(location_raw) if location_raw else None
            metro = geo[2] if geo else normalize_location_text(location_raw)

            workplace = raw.get("workplaceTypes", [])
            if isinstance(workplace, list):
                workplace = [w.lower() for w in workplace]
                if "remote" in workplace:
                    remote_type = "Remote"
                elif "hybrid" in workplace:
                    remote_type = "Hybrid"
                else:
                    remote_type = "Onsite"
            else:
                remote_type = "Onsite"

            employment_details = raw.get("employmentDetails", [])
            employment_type = "Full-time"
            if isinstance(employment_details, list) and employment_details:
                emp = employment_details[0].lower()
                if "part" in emp: employment_type = "Part-time"
                elif "contract" in emp: employment_type = "Contract"
                elif "intern" in emp: employment_type = "Internship"

            salary_info = raw.get("salary", {})
            sal_min = salary_info.get("minimum") if isinstance(salary_info, dict) else None
            sal_max = salary_info.get("maximum") if isinstance(salary_info, dict) else None

            description = raw.get("descriptionFragment", raw.get("description", ""))
            skills = extract_skills(description)
            identity_key = build_job_identity_key(company_name, title_normalized, metro)

            date_str = raw.get("postedDate")
            date_posted = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else None

            return {
                "source": self.source_name,
                "external_id": raw.get("id") or raw.get("jobId"),
                "source_url": f"https://www.dice.com/jobs/detail/{raw.get('id', '')}",
                "company_name": company_name,
                "title_raw": title_raw,
                "title_normalized": title_normalized,
                "seniority": seniority,
                "location_raw": location_raw,
                "city": None,
                "state": None,
                "country": raw.get("country", "US"),
                "metro_area": metro,
                "latitude": geo[0] if geo else None,
                "longitude": geo[1] if geo else None,
                "remote_type": remote_type,
                "salary_min": int(sal_min) if sal_min else None,
                "salary_max": int(sal_max) if sal_max else None,
                "salary_listed": bool(sal_min),
                "employment_type": employment_type,
                "description_raw": description,
                "skills": skills,
                "date_posted": date_posted,
                "job_identity_key": identity_key,
            }
        except Exception as e:
            log.error("dice_parse_error", error=str(e))
            return None


async def scrape_dice(max_pages: int = None) -> list[dict]:
    scraper = DiceScraper(max_pages)
    return await scraper.scrape()
