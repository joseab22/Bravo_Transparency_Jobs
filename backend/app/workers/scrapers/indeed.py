"""Indeed-targeted JSearch collection."""
from __future__ import annotations

from app.workers.scrapers.jsearch import JSearchScraper


class IndeedScraper(JSearchScraper):
    source_name = "indeed"
    expected_source = "indeed"
    publisher_filter = "indeed"


async def scrape_indeed(max_pages: int | None = None) -> list[dict]:
    return await IndeedScraper(max_pages).scrape()
