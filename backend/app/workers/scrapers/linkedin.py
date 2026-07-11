"""LinkedIn-targeted JSearch collection."""
from __future__ import annotations

from app.workers.scrapers.jsearch import JSearchScraper


class LinkedInScraper(JSearchScraper):
    source_name = "linkedin"
    expected_source = "linkedin"
    publisher_filter = "linkedin"


async def scrape_linkedin(max_pages: int | None = None) -> list[dict]:
    return await LinkedInScraper(max_pages).scrape()
