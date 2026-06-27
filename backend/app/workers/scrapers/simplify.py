"""
Simplify scraper adapter.

Simplify (simplify.jobs) aggregates and normalizes job postings,
with a focus on early-career and new-grad roles.

Integration options:

OPTION A — Simplify Public Jobs Feed (JSON):
  Simplify maintains public GitHub repos with job data:
  https://github.com/SimplifyJobs/Summer2024-Internships
  https://github.com/SimplifyJobs/New-Grad-Positions
  These are JSON files updated regularly via GitHub Actions.
  No API key required. Parse via raw GitHub content URLs.
  Env vars: none required

OPTION B — Simplify API (if/when they open a public API):
  Env vars: SIMPLIFY_API_KEY, SIMPLIFY_API_BASE_URL

NOTE: Start with Option A — their public GitHub repos are high quality,
well-normalized, and update daily. Excellent source for entry-level roles.
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

# Simplify public GitHub JSON feeds
SIMPLIFY_FEEDS = {
    "new_grad": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
    "internships": "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/.github/scripts/listings.json",
}


class SimplifyScraper(BaseScraperAdapter):
    source_name = "simplify"

    def __init__(self, max_pages: int = None):
        super().__init__(max_pages or 1)  # GitHub feeds are single-page
        self.api_key = getattr(settings, "simplify_api_key", "")
        self.use_github_feeds = not bool(self.api_key)

    async def fetch_jobs(self, query: str, page: int = 1) -> list:
        """For GitHub feed mode, query is ignored — we pull all and filter."""
        if self.use_github_feeds:
            return await self._fetch_github_feed()
        return await self._fetch_api(query, page)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_github_feed(self) -> list:
        all_jobs = []
        async with httpx.AsyncClient() as client:
            for feed_name, url in SIMPLIFY_FEEDS.items():
                try:
                    response = await client.get(url, timeout=30.0)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, list):
                        all_jobs.extend(data)
                    log.info("simplify_feed_fetched", feed=feed_name, count=len(data) if isinstance(data, list) else 0)
                except Exception as e:
                    log.error("simplify_feed_error", feed=feed_name, error=str(e))
        return all_jobs

    async def _fetch_api(self, query: str, page: int) -> list:
        # Future: implement Simplify API when available
        log.warning("simplify_api_not_implemented", hint="Use SIMPLIFY_API_KEY once Simplify opens public API access.")
        return []

    def extract_job_list(self, raw_response) -> list:
        if isinstance(raw_response, list):
            return raw_response
        return []

    async def scrape(self, queries: list[str] = None) -> list[dict]:
        """Override: GitHub feed is a single pull, no per-query pagination."""
        if self.use_github_feeds:
            raw_jobs = await self._fetch_github_feed()
            results = []
            for raw in raw_jobs:
                parsed = self.parse_job(raw)
                if parsed:
                    results.append(parsed)
            log.info("simplify_scrape_complete", total=len(results))
            return results
        return await super().scrape(queries)

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = raw.get("title", raw.get("role", ""))
            company_name = raw.get("company_name", raw.get("company", ""))
            if not title_raw or not company_name:
                return None

            # Simplify stores locations as a list
            locations = raw.get("locations", raw.get("location", []))
            if isinstance(locations, list) and locations:
                location_raw = locations[0]
            elif isinstance(locations, str):
                location_raw = locations
            else:
                location_raw = ""

            title_normalized = normalize_title(title_raw)
            seniority = extract_seniority(title_raw)
            geo = geocode_location(location_raw) if location_raw else None
            metro = geo[2] if geo else normalize_location_text(location_raw)

            is_remote = "remote" in location_raw.lower() if location_raw else False
            description = raw.get("description", "")
            skills = extract_skills(description)
            identity_key = build_job_identity_key(company_name, title_normalized, metro)

            date_str = raw.get("date_posted") or raw.get("date_updated")
            date_posted = None
            if date_str:
                try:
                    date_posted = datetime.fromisoformat(str(date_str))
                except Exception:
                    pass

            return {
                "source": self.source_name,
                "external_id": str(raw.get("id", raw.get("url", ""))),
                "source_url": raw.get("url") or raw.get("apply_url"),
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
                "remote_type": "Remote" if is_remote else "Onsite",
                "salary_min": None,
                "salary_max": None,
                "salary_listed": False,
                "employment_type": "Full-time" if "internship" not in title_raw.lower() else "Internship",
                "description_raw": description,
                "skills": skills,
                "date_posted": date_posted,
                "job_identity_key": identity_key,
            }
        except Exception as e:
            log.error("simplify_parse_error", error=str(e))
            return None


async def scrape_simplify(max_pages: int = None) -> list[dict]:
    scraper = SimplifyScraper(max_pages)
    return await scraper.scrape()
