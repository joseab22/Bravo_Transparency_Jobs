"""Simplify public-feed adapter for current early-career technology roles."""
from __future__ import annotations

import re
from typing import Optional

import structlog

from app.core.config import settings
from app.services.normalizer import extract_skills, normalize_employment_type, parse_datetime
from app.workers.scrapers.base import BaseScraperAdapter

log = structlog.get_logger()

_MIN_PLAUSIBLE_ANNUAL_SALARY = 1_000


def _parse_salary_values(text: str) -> list[int]:
    """Extract plausible annual-salary figures from free-form salary text.

    Handles comma-grouped ("$95,000"), ungrouped ("$95000"), and "k"-suffixed
    ("100k") figures uniformly, unlike a comma-grouping-only regex, which
    silently splits an ungrouped number into unrelated fragments. Figures
    below a plausible annual-salary floor are dropped rather than kept as
    wrong data.
    """
    values: list[int] = []
    for number_text, k_suffix in re.findall(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([kK])?", text):
        if not number_text:
            continue
        try:
            number = float(number_text.replace(",", ""))
        except ValueError:
            continue
        if k_suffix:
            number *= 1000
        if number < _MIN_PLAUSIBLE_ANNUAL_SALARY:
            continue
        values.append(round(number))
    return values


class SimplifyScraper(BaseScraperAdapter):
    source_name = "simplify"

    def __init__(self, max_pages: int | None = None):
        super().__init__(max_pages=1, max_records=settings.simplify_max_records)
        self.feeds = {
            "new_grad": settings.simplify_new_grad_feed_url,
            "internships": settings.simplify_internship_feed_url,
        }

    async def fetch_jobs(self, query: str, page: int = 1) -> list:
        data = await self.request_json(self.feeds[query], headers={"Accept": "application/json"})
        log.info("simplify_feed_fetched", feed=query, count=len(data) if isinstance(data, list) else 0)
        return data if isinstance(data, list) else []

    async def scrape(self, queries: Optional[list[str]] = None) -> list[dict]:
        return await super().scrape(list(self.feeds))

    def parse_job(self, raw: dict) -> Optional[dict]:
        # A closed/inactive record is not silently dropped: it still carries
        # conclusive negative evidence for whatever existing row it matches
        # (see provider_reports_closed below), even though it is never used
        # to create a new row of its own.
        closed = str(raw.get("is_closed", "false")).lower() in {"true", "1", "yes"}
        inactive = str(raw.get("active", "true")).lower() in {"false", "0", "no"}
        title = raw.get("title") or raw.get("role") or ""
        company = raw.get("company_name") or raw.get("company") or ""
        if isinstance(company, dict):
            company = company.get("name", "")
        if not title or not company:
            return None

        raw_locations = raw.get("locations") or raw.get("location") or []
        if isinstance(raw_locations, str):
            locations = [raw_locations]
        elif isinstance(raw_locations, list):
            locations = [str(item.get("location") or item.get("name") or item) if isinstance(item, dict) else str(item) for item in raw_locations]
        else:
            locations = []
        location = " | ".join(dict.fromkeys(value.strip() for value in locations if value and value.strip())) or None

        description = raw.get("description") or raw.get("description_text") or ""
        external_id = raw.get("id") or raw.get("job_id") or raw.get("slug")
        source_url = raw.get("url") or raw.get("application_url") or raw.get("link")
        date_posted = parse_datetime(raw.get("date_posted") or raw.get("date") or raw.get("created_at"))
        employment = normalize_employment_type(raw.get("type"), title)
        salary_text = str(raw.get("salary") or "")
        salary_values = _parse_salary_values(salary_text)

        return {
            "source": self.source_name,
            "external_id": str(external_id) if external_id not in (None, "") else None,
            "source_url": source_url,
            "company_name": str(company),
            "title_raw": title,
            "location_raw": location,
            "remote_type": "Remote" if any("remote" in value.lower() for value in locations) else raw.get("remote_type"),
            "employment_type": employment,
            "salary_min": min(salary_values) if salary_values else None,
            "salary_max": max(salary_values) if salary_values else None,
            "salary_period": "year",
            "description_raw": description,
            "skills": extract_skills(description),
            "date_posted": date_posted,
            **({"provider_reports_closed": True} if (closed or inactive) else {}),
        }


async def scrape_simplify(max_pages: int | None = None) -> list[dict]:
    return await SimplifyScraper(max_pages).scrape()
