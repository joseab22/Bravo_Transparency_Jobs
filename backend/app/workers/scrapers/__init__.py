"""
Scraper registry.

Import all adapters here so worker tasks can reference them by source name.
"""
from app.workers.scrapers.base import BaseScraperAdapter
from app.workers.scrapers.indeed import scrape_indeed
from app.workers.scrapers.linkedin import scrape_linkedin
from app.workers.scrapers.glassdoor import scrape_glassdoor
from app.workers.scrapers.ziprecruiter import scrape_ziprecruiter
from app.workers.scrapers.dice import scrape_dice
from app.workers.scrapers.monster import scrape_monster
from app.workers.scrapers.jobright import scrape_jobright
from app.workers.scrapers.simplify import scrape_simplify

SCRAPER_REGISTRY = {
    "indeed": scrape_indeed,
    "linkedin": scrape_linkedin,
    "glassdoor": scrape_glassdoor,
    "ziprecruiter": scrape_ziprecruiter,
    "dice": scrape_dice,
    "monster": scrape_monster,
    "jobright": scrape_jobright,
    "simplify": scrape_simplify,
}

__all__ = [
    "BaseScraperAdapter",
    "SCRAPER_REGISTRY",
    "scrape_indeed",
    "scrape_linkedin",
    "scrape_glassdoor",
    "scrape_ziprecruiter",
    "scrape_dice",
    "scrape_monster",
    "scrape_jobright",
    "scrape_simplify",
]
