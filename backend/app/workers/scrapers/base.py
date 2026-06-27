"""
Base scraper interface.

All source adapters inherit from BaseScraperAdapter and implement:
  - fetch_jobs()     → raw API/HTML response
  - parse_job()      → normalized job dict
  - scrape()         → orchestrates fetch + parse, returns list of job dicts

The normalized job dict schema is the same for all sources:
{
    "source":           str   (JobSource enum value)
    "external_id":      str | None
    "source_url":       str | None
    "company_name":     str
    "title_raw":        str
    "title_normalized": str
    "seniority":        str | None
    "location_raw":     str | None
    "city":             str | None
    "state":            str | None
    "country":          str   (default "US")
    "metro_area":       str | None
    "latitude":         float | None
    "longitude":        float | None
    "remote_type":      str | None   ("Remote" | "Hybrid" | "Onsite")
    "salary_min":       int | None
    "salary_max":       int | None
    "salary_listed":    bool
    "employment_type":  str          ("Full-time" | "Part-time" | "Contract" | "Internship")
    "description_raw":  str | None
    "skills":           list[dict]   [{skill, skill_normalized, skill_category}]
    "date_posted":      datetime | None
    "job_identity_key": str
}
"""

from abc import ABC, abstractmethod
from typing import Optional
import structlog

log = structlog.get_logger()


class BaseScraperAdapter(ABC):
    """Abstract base class for all job source adapters."""

    source_name: str = ""  # Must match JobSource enum value exactly

    def __init__(self, max_pages: int = 10):
        self.max_pages = max_pages

    @abstractmethod
    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        """
        Fetch raw job data from the source for a given query and page.
        Returns the raw response (dict, list, or HTML string).
        """
        ...

    @abstractmethod
    def parse_job(self, raw: dict) -> Optional[dict]:
        """
        Parse a single raw job record into the normalized job dict schema.
        Returns None if the record should be skipped.
        """
        ...

    async def scrape(self, queries: list[str] = None) -> list[dict]:
        """
        Orchestrate fetching and parsing for all queries.
        Returns a list of normalized job dicts ready for ingestion.
        Subclasses can override this for source-specific pagination logic.
        """
        queries = queries or self.default_queries()
        all_jobs = []

        for query in queries:
            log.info("scraper_query_start", source=self.source_name, query=query)
            for page in range(1, self.max_pages + 1):
                try:
                    raw_response = await self.fetch_jobs(query, page)
                    raw_jobs = self.extract_job_list(raw_response)

                    if not raw_jobs:
                        log.info("scraper_no_more_results", source=self.source_name, query=query, page=page)
                        break

                    for raw in raw_jobs:
                        parsed = self.parse_job(raw)
                        if parsed:
                            all_jobs.append(parsed)

                    await self.rate_limit_sleep()

                except Exception as e:
                    log.error("scraper_page_error", source=self.source_name, query=query, page=page, error=str(e))
                    break

        log.info("scraper_complete", source=self.source_name, total=len(all_jobs))
        return all_jobs

    def extract_job_list(self, raw_response) -> list:
        """
        Extract the list of job records from the raw API response.
        Override in subclass if the response format differs.
        """
        if isinstance(raw_response, list):
            return raw_response
        if isinstance(raw_response, dict):
            return raw_response.get("data", raw_response.get("jobs", raw_response.get("results", [])))
        return []

    async def rate_limit_sleep(self):
        """Courtesy sleep between requests. Override per source."""
        import asyncio
        await asyncio.sleep(0.5)

    def default_queries(self) -> list[str]:
        """Default job title queries. Override or extend per source."""
        return [
            "data analyst",
            "data engineer",
            "data scientist",
            "machine learning engineer",
            "software engineer",
            "analytics engineer",
            "business analyst",
        ]
