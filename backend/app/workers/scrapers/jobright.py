"""
Jobright scraper adapter.

Jobright is an AI-powered job aggregator with a curated feed.

Integration options:

OPTION A — Jobright API (requires account + API access request):
  Contact Jobright at https://jobright.ai for API access.
  They provide a structured JSON feed with pre-normalized titles and skills.
  Env vars: JOBRIGHT_API_KEY, JOBRIGHT_API_BASE_URL

OPTION B — RSS/JSON feed parsing:
  Jobright publishes role-specific feeds. Parse with feedparser.
  Env vars: JOBRIGHT_FEED_URL

NOTE: Jobright already does some NLP normalization on job titles and skills.
Their feed is a good signal-quality cross-check against our own normalizer.
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


class JobrightScraper(BaseScraperAdapter):
    source_name = "jobright"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or settings.max_pages_per_source)
        self.api_key = getattr(settings, "jobright_api_key", "")
        self.base_url = getattr(settings, "jobright_api_base_url", "https://api.jobright.ai/v1")

    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        if not self.api_key:
            log.warning(
                "jobright_no_api_key",
                hint="Request Jobright API access and set JOBRIGHT_API_KEY in .env",
            )
            return {"jobs": [], "total": 0}

        return await self.request_json(
            f"{self.base_url}/jobs/search",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            params={
                "q": query,
                "page": page,
                "limit": 20,
                "country": "US",
                "postedWithin": "7d",
            },
        )

    def extract_job_list(self, raw_response) -> list:
        if isinstance(raw_response, dict):
            return raw_response.get("jobs", raw_response.get("data", []))
        return []

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = raw.get("title", raw.get("jobTitle", ""))
            company_name = raw.get("company", raw.get("companyName", ""))
            if not title_raw or not company_name:
                return None

            location_raw = raw.get("location", raw.get("locationString", ""))
            title_normalized = normalize_title(title_raw)
            seniority = extract_seniority(title_raw)
            geo = geocode_location(location_raw) if location_raw else None
            metro = geo[2] if geo else normalize_location_text(location_raw)

            # Jobright pre-extracts skills; use theirs if available, else extract
            raw_skills = raw.get("skills", [])
            if raw_skills and isinstance(raw_skills, list):
                skills = [
                    {"skill": s, "skill_normalized": s.lower(), "skill_category": None}
                    for s in raw_skills if isinstance(s, str)
                ]
            else:
                description = raw.get("description", "")
                skills = extract_skills(description)

            description = raw.get("description", raw.get("descriptionHtml", ""))
            identity_key = build_job_identity_key(company_name, title_normalized, metro)

            date_str = raw.get("postedAt") or raw.get("datePosted")
            date_posted = None
            if date_str:
                try:
                    date_posted = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            return {
                "source": self.source_name,
                "external_id": str(raw.get("id", raw.get("jobId", ""))),
                "source_url": raw.get("url") or raw.get("applyUrl"),
                "company_name": company_name,
                "title_raw": title_raw,
                "title_normalized": title_normalized,
                "seniority": seniority,
                "location_raw": location_raw,
                "city": raw.get("city"),
                "state": raw.get("state"),
                "country": raw.get("country", "US"),
                "metro_area": metro,
                "latitude": geo[0] if geo else None,
                "longitude": geo[1] if geo else None,
                "remote_type": raw.get("workMode", "Onsite"),
                "salary_min": raw.get("salaryMin"),
                "salary_max": raw.get("salaryMax"),
                "salary_listed": bool(raw.get("salaryMin")),
                "employment_type": raw.get("employmentType", "Full-time"),
                "description_raw": description,
                "skills": skills,
                "date_posted": date_posted,
                "job_identity_key": identity_key,
            }
        except Exception as e:
            log.error("jobright_parse_error", error=str(e))
            return None


async def scrape_jobright(max_pages: int = None) -> list[dict]:
    scraper = JobrightScraper(max_pages)
    return await scraper.scrape()
