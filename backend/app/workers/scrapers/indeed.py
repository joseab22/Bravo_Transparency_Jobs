"""
Indeed scraper.

Uses the JSearch API via RapidAPI (most reliable programmatic access).
Falls back to direct scraping with httpx + BeautifulSoup.

Rate limits: 100 requests/month on free tier, 500 on basic.
Set RAPIDAPI_KEY in .env to enable.
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
    normalize_location_text, extract_skills, build_job_identity_key,
    embed_text,
)

log = structlog.get_logger()

JSEARCH_BASE = "https://jsearch.p.rapidapi.com"
RAPIDAPI_HEADERS = {
    "X-RapidAPI-Key": settings.rapidapi_key,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}

# Job queries to run — expand this list
SEARCH_QUERIES = [
    "data analyst",
    "data engineer",
    "data scientist",
    "machine learning engineer",
    "software engineer",
    "business analyst",
    "analytics engineer",
    "quantitative analyst",
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_jsearch_page(client: httpx.AsyncClient, query: str, page: int = 1) -> dict:
    response = await client.get(
        f"{JSEARCH_BASE}/search",
        headers=RAPIDAPI_HEADERS,
        params={
            "query": query,
            "page": str(page),
            "num_pages": "1",
            "date_posted": "week",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def parse_jsearch_job(raw: dict) -> Optional[dict]:
    """Transform JSearch API result into our internal job dict."""
    try:
        title_raw = raw.get("job_title", "")
        company_name = raw.get("employer_name", "")
        location_raw = f"{raw.get('job_city', '')}, {raw.get('job_state', '')}".strip(", ")

        if not title_raw or not company_name:
            return None

        title_normalized = normalize_title(title_raw)
        seniority = extract_seniority(title_raw)

        # Location
        geo = geocode_location(location_raw) if location_raw else None
        lat = geo[0] if geo else None
        lon = geo[1] if geo else None
        metro = geo[2] if geo else normalize_location_text(location_raw)

        # Remote type
        remote_raw = raw.get("job_is_remote", False)
        remote_type = "Remote" if remote_raw else "Onsite"

        # Salary
        sal_min = raw.get("job_min_salary")
        sal_max = raw.get("job_max_salary")
        sal_period = raw.get("job_salary_period", "")
        # Normalize to annual
        if sal_period == "HOUR" and sal_min:
            sal_min = int(sal_min * 2080)
            sal_max = int(sal_max * 2080) if sal_max else None
        elif sal_period == "MONTH" and sal_min:
            sal_min = int(sal_min * 12)
            sal_max = int(sal_max * 12) if sal_max else None

        description = raw.get("job_description", "")
        skills = extract_skills(description)
        embedding = embed_text(description[:1000]) if description else None  # truncate for speed

        identity_key = build_job_identity_key(company_name, title_normalized, metro)

        date_posted_str = raw.get("job_posted_at_datetime_utc")
        date_posted = datetime.fromisoformat(date_posted_str.replace("Z", "+00:00")) if date_posted_str else None

        return {
            "source": "indeed",
            "external_id": raw.get("job_id"),
            "source_url": raw.get("job_apply_link") or raw.get("job_google_link"),
            "company_name": company_name,
            "title_raw": title_raw,
            "title_normalized": title_normalized,
            "seniority": seniority,
            "location_raw": location_raw,
            "city": raw.get("job_city"),
            "state": raw.get("job_state"),
            "country": raw.get("job_country", "US"),
            "metro_area": metro,
            "latitude": lat,
            "longitude": lon,
            "remote_type": remote_type,
            "salary_min": int(sal_min) if sal_min else None,
            "salary_max": int(sal_max) if sal_max else None,
            "salary_listed": bool(sal_min),
            "employment_type": _map_employment_type(raw.get("job_employment_type")),
            "description_raw": description,
            "description_embedding": embedding,
            "skills": skills,
            "date_posted": date_posted,
            "job_identity_key": identity_key,
        }
    except Exception as e:
        log.error("parse_jsearch_job_error", error=str(e), raw_job=raw.get("job_id"))
        return None


def _map_employment_type(raw: Optional[str]) -> str:
    if not raw:
        return "Full-time"
    raw = raw.upper()
    if "PART" in raw:
        return "Part-time"
    if "CONTRACT" in raw or "TEMP" in raw:
        return "Contract"
    if "INTERN" in raw:
        return "Internship"
    return "Full-time"


async def scrape_indeed(max_pages: int = None) -> list[dict]:
    """
    Scrape Indeed via JSearch API.
    Returns list of normalized job dicts ready for DB ingestion.
    """
    max_pages = max_pages or settings.max_pages_per_source
    all_jobs = []

    async with httpx.AsyncClient() as client:
        for query in SEARCH_QUERIES:
            log.info("scraping_indeed", query=query)
            for page in range(1, max_pages + 1):
                try:
                    data = await fetch_jsearch_page(client, query, page)
                    raw_jobs = data.get("data", [])
                    if not raw_jobs:
                        break

                    for raw in raw_jobs:
                        parsed = parse_jsearch_job(raw)
                        if parsed:
                            all_jobs.append(parsed)

                    await asyncio.sleep(0.5)  # rate limit courtesy

                except httpx.HTTPStatusError as e:
                    log.error("jsearch_http_error", status=e.response.status_code, query=query)
                    break
                except Exception as e:
                    log.error("jsearch_error", error=str(e), query=query)
                    break

    log.info("scrape_indeed_complete", total_jobs=len(all_jobs))
    return all_jobs
