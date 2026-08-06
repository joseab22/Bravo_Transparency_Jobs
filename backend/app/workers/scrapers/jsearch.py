"""JSearch collection with publisher attribution and protected Pro-plan usage.

JSearch is the collection provider. The publisher carrying an application link
(LinkedIn, Indeed, a company career site, and so on) is stored separately.
Every distinct apply URL is retained as a source sighting. Publisher/domain
exclusions are optional and controlled through environment settings.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
import structlog

from app.core.config import settings
from app.services.normalizer import (
    annualize_salary,
    build_job_identity_key,
    build_source_sighting_key,
    extract_seniority,
    extract_skills,
    normalize_location_text,
    normalize_remote_type,
    normalize_source_url,
    normalize_title,
)
from app.services.request_budget import RapidAPIRequestBudget, RequestBudgetExceeded
from app.workers.scrapers.base import (
    BaseScraperAdapter,
    ScraperBudgetExhaustedError,
)

log = structlog.get_logger()
JSEARCH_BASE = "https://api.openwebninja.com/jsearch"

KNOWN_PUBLISHERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("simplify", ("simplify", "simplify.jobs")),
    ("linkedin", ("linkedin", "linkedin.com")),
    ("indeed", ("indeed", "indeed.com")),
    ("glassdoor", ("glassdoor", "glassdoor.com")),
    ("ziprecruiter", ("ziprecruiter", "ziprecruiter.com")),
    ("dice", ("dice", "dice.com")),
    ("monster", ("monster", "monster.com")),
    ("jobright", ("jobright", "jobright.ai")),
)


def _ascii(value: Any) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _ascii(value).lower()).strip("-")


def _host(value: Any) -> str:
    url = normalize_source_url(value)
    if not url:
        return ""
    return urlparse(url).netloc.lower().removeprefix("www.")


def _domain_matches(host: str, domain: str) -> bool:
    return bool(host and (host == domain or host.endswith(f".{domain}")))


def is_excluded_publisher(publisher: Any, source_url: Any = None) -> bool:
    label = re.sub(r"\s+", " ", _ascii(publisher).lower()).strip()
    slug = _slug(label).replace("-", " ")
    host = _host(source_url)
    if any(value in {label, slug} or value in label for value in settings.jsearch_excluded_publisher_set):
        return True
    return any(_domain_matches(host, domain) for domain in settings.jsearch_excluded_domain_set)


def normalize_publisher(
    publisher: Any,
    source_url: Any = None,
    *,
    employer_name: Any = None,
    employer_website: Any = None,
    is_direct: bool = False,
) -> tuple[str, str]:
    """Return a stable source key and user-facing publisher label."""
    label = str(publisher or "").strip()
    host = _host(source_url)
    haystack = f"{label.lower()} {host}"

    for source, markers in KNOWN_PUBLISHERS:
        if any(marker in haystack for marker in markers):
            return source, label or source.replace("-", " ").title()

    employer_host = _host(employer_website)
    employer_slug = _slug(employer_name)
    label_slug = _slug(label)
    looks_like_employer_careers = bool(
        employer_slug
        and employer_slug in label_slug
        and any(marker in label_slug for marker in ("career", "careers", "job", "jobs"))
    )
    if (
        is_direct
        or (employer_host and _domain_matches(host, employer_host))
        or looks_like_employer_careers
    ):
        return "company_site", label or f"{str(employer_name or 'Company').strip()} Careers"

    if label:
        return (_slug(label) or "jsearch")[:100], label[:255]
    if host:
        return (_slug(host) or "jsearch")[:100], host[:255]
    return "jsearch", "JSearch"
    
def extract_source_options(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract every distinct allowed publisher/apply URL."""
    candidates: list[dict[str, Any]] = [{
        "publisher": raw.get("job_publisher"),
        "apply_link": raw.get("job_apply_link") or raw.get("job_google_link"),
        "is_direct": raw.get("job_apply_is_direct", False),
    }]
    candidates.extend(item for item in (raw.get("apply_options") or []) if isinstance(item, dict))

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    external_id = str(raw.get("job_id")) if raw.get("job_id") not in (None, "") else None
    employer_name = raw.get("employer_name")
    employer_website = raw.get("employer_website")

    for item in candidates:
        publisher = item.get("publisher") or item.get("job_publisher")
        source_url = normalize_source_url(
            item.get("apply_link")
            or item.get("job_apply_link")
            or item.get("apply_url")
            or item.get("url")
            or item.get("link")
        )
        if is_excluded_publisher(publisher, source_url):
            continue
        is_direct = bool(item.get("is_direct", False))
        source, publisher_name = normalize_publisher(
            publisher,
            source_url,
            employer_name=employer_name,
            employer_website=employer_website,
            is_direct=is_direct,
        )
        sighting_key = build_source_sighting_key(source, source_url, external_id)
        if sighting_key in seen:
            continue
        seen.add(sighting_key)
        result.append({
            "sighting_key": sighting_key,
            "source": source,
            "publisher_name": publisher_name,
            "collection_provider": "jsearch",
            "source_url": source_url,
            "external_id": external_id,
            "applicant_count": None,
            "is_direct": is_direct,
        })

    return result


def select_primary_source(
    raw: dict[str, Any], expected_source: Optional[str] = None
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    options = extract_source_options(raw)
    expected = (expected_source or "").lower().strip()
    if expected:
        for option in options:
            if option["source"] == expected:
                return option, options
        # A targeted scrape (e.g. a LinkedIn/Indeed-only run) found no option
        # actually attributed to the expected publisher. Falling back to some
        # other publisher's option here would silently mislabel it as if it
        # came from the targeted board, so the caller drops the record
        # instead of storing it under the wrong source.
        return None, options
    # The first option comes from JSearch's primary job_publisher/apply link.
    # Keep that attribution as the row's primary source while retaining every
    # direct/company and alternate-board link in source_options.
    return (options[0] if options else None), options


class JSearchScraper(BaseScraperAdapter):
    """Generic JSearch adapter with optional publisher targeting."""

    source_name = "jsearch"
    expected_source: Optional[str] = None
    publisher_filter: Optional[str] = None

    def __init__(self, max_pages: int | None = None):
        super().__init__(
            max_pages or settings.jsearch_pages_per_query,
            minimum_delay=0.25,
            maximum_delay=0.50,
        )
        self._request_budget = RapidAPIRequestBudget(
            settings.redis_url,
            namespace="jsearch",
            monthly_limit=settings.jsearch_monthly_request_limit,
            reserve=settings.jsearch_request_reserve,
        )
        self._query_cursors: dict[str, str] = {}

    async def before_request(self, url: str) -> None:
        if url.startswith(JSEARCH_BASE):
            try:
                await self._request_budget.reserve_request()
            except RequestBudgetExceeded as exc:
                raise ScraperBudgetExhaustedError(str(exc)) from exc

    async def after_response(self, response: httpx.Response) -> None:
        if str(response.request.url).startswith(JSEARCH_BASE):
            await self._request_budget.update_from_headers(response.headers)

    async def close(self) -> None:
        await super().close()
        try:
            status = await self._request_budget.status()
            log.info("jsearch_quota_status", **status.as_dict())
        except Exception as exc:
            # Quota telemetry must never turn a successful scrape into a failure.
            log.warning("jsearch_quota_status_unavailable", error=str(exc))
        finally:
            await self._request_budget.close()

    def _search_query(self, query: str) -> str:
        value = query.strip()
        location = settings.jsearch_location.strip()

        if location and location.lower() not in value.lower():
            value = f"{value} in {location}"

        if self.publisher_filter:
            value = f"{value} via {self.publisher_filter}"

        for domain in sorted(settings.jsearch_excluded_domain_set):
            value = f"{value} -site:{domain}"

        return value

    def extract_job_list(self, payload: Any) -> list[dict[str, Any]]:
        """Extract jobs from RapidAPI-style and direct OpenWeb Ninja responses."""
        if not isinstance(payload, dict):
            return []

        data = payload.get("data")

        # Older/RapidAPI-style response:
        # {"data": [{...}, {...}]}
        if isinstance(data, list):
            return [job for job in data if isinstance(job, dict)]

        # Direct OpenWeb Ninja search-v2 response:
        # {"data": {"jobs": [{...}], "cursor": "..."}}
        if isinstance(data, dict):
            jobs = data.get("jobs", [])
            if isinstance(jobs, list):
                return [job for job in jobs if isinstance(job, dict)]

        return []

    async def fetch_jobs(self, query: str, page: int = 1) -> dict:
        if not settings.openwebninja_api_key:
            raise RuntimeError(
                "OPENWEBNINJA_API_KEY is required for JSearch collection"
            )

        params = {
            "query": self._search_query(query),
            "country": settings.jsearch_country,
            "language": settings.jsearch_language,
            "date_posted": settings.jsearch_date_posted,
        }

        if page > 1:
            cursor = self._query_cursors.get(query)
            if not cursor:
                return {"data": {"jobs": []}}
            params["cursor"] = cursor

        payload = await self.request_json(
            f"{JSEARCH_BASE}/search-v2",
            headers={
                "X-API-Key": settings.openwebninja_api_key,
            },
            params=params,
        )

        if isinstance(payload, dict):
            nested_data = payload.get("data")
            nested_data = nested_data if isinstance(nested_data, dict) else {}

            cursor = (
                nested_data.get("cursor")
                or payload.get("cursor")
                or nested_data.get("next_cursor")
                or payload.get("next_cursor")
                or nested_data.get("next_page_cursor")
                or payload.get("next_page_cursor")
            )

            jobs = self.extract_job_list(payload)

            log.info(
                "jsearch_response_summary",
                status=payload.get("status"),
                data_type=type(payload.get("data")).__name__,
                parsed_job_count=len(jobs),
                cursor_found=bool(cursor),
            )

            if cursor:
                self._query_cursors[query] = str(cursor)
            else:
                self._query_cursors.pop(query, None)

        return payload

    def parse_job(self, raw: dict) -> Optional[dict]:
        try:
            title_raw = str(raw.get("job_title") or "").strip()
            company_name = str(raw.get("employer_name") or "").strip()
            if not title_raw or not company_name:
                return None

            primary, source_options = select_primary_source(raw, self.expected_source)
            if primary is None:
                log.info(
                    "jsearch_job_excluded",
                    job_id=raw.get("job_id"),
                    publisher=raw.get("job_publisher"),
                    reason="only excluded publishers were returned",
                )
                return None

            location_raw = str(raw.get("job_location") or "").strip()
            if not location_raw:
                location_raw = f"{raw.get('job_city', '')}, {raw.get('job_state', '')}".strip(", ")
            if not location_raw and raw.get("job_country"):
                location_raw = str(raw["job_country"])

            description = str(raw.get("job_description") or "")
            salary_min, salary_max = annualize_salary(
                raw.get("job_min_salary"),
                raw.get("job_max_salary"),
                raw.get("job_salary_period") or "year",
            )
            experience_min, experience_max = self._experience_years(raw)
            education = self._education_required(raw)
            employment = raw.get("job_employment_type_text") or raw.get("job_employment_type")
            if not employment and isinstance(raw.get("job_employment_types"), list):
                employment = " ".join(str(item) for item in raw["job_employment_types"])
            categories = raw.get("job_occupational_categories")
            department = ", ".join(map(str, categories)) if isinstance(categories, list) else categories
            remote_type = "Remote" if raw.get("job_is_remote") else normalize_remote_type(
                None, f"{location_raw} {title_raw} {description[:500]}"
            )
            title_normalized = normalize_title(title_raw)
            metro = normalize_location_text(location_raw)

            return {
                "source": primary["source"],
                "publisher_name": primary["publisher_name"],
                "collection_provider": "jsearch",
                "source_options": source_options,
                "external_id": raw.get("job_id"),
                "source_url": primary.get("source_url") or normalize_source_url(raw.get("job_google_link")),
                "company_name": company_name,
                "company_website": raw.get("employer_website"),
                "title_raw": title_raw,
                "title_normalized": title_normalized,
                "seniority": extract_seniority(title_raw),
                "location_raw": location_raw,
                "city": raw.get("job_city"),
                "state": raw.get("job_state"),
                "country": raw.get("job_country") or "US",
                "metro_area": metro,
                "latitude": raw.get("job_latitude"),
                "longitude": raw.get("job_longitude"),
                "remote_type": remote_type,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_currency": raw.get("job_salary_currency") or "USD",
                "salary_listed": salary_min is not None or salary_max is not None,
                "employment_type": employment,
                "education_required": education,
                "experience_years_min": experience_min,
                "experience_years_max": experience_max,
                "department": department,
                "industry": raw.get("employer_company_type") or raw.get("job_naics_name"),
                "description_raw": description,
                "skills": extract_skills(description),
                "date_posted": self._parse_date(raw),
                "job_identity_key": build_job_identity_key(company_name, title_normalized, metro),
            }
        except Exception as exc:
            log.error("jsearch_parse_error", source=self.source_name, error=str(exc))
            return None

    def default_queries(self) -> list[str]:
        return settings.jsearch_query_list

    @staticmethod
    def _parse_date(raw: dict[str, Any]) -> Optional[datetime]:
        value = raw.get("job_posted_at_datetime_utc") or raw.get("job_posted_at_timestamp")
        if not value:
            return None
        if isinstance(value, (int, float)):
            try:
                return datetime.utcfromtimestamp(float(value))
            except (OverflowError, OSError, ValueError):
                return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _experience_years(raw: dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
        details = raw.get("job_required_experience")
        if not isinstance(details, dict):
            return None, None
        months = details.get("required_experience_in_months")
        if months in (None, ""):
            return None, None
        try:
            years = max(float(months) / 12.0, 0.0)
            return math.floor(years), math.ceil(years)
        except (TypeError, ValueError):
            return None, None

    @staticmethod
    def _education_required(raw: dict[str, Any]) -> Optional[str]:
        value = raw.get("job_required_education")
        if isinstance(value, str):
            return value[:200]
        if not isinstance(value, dict):
            return None
        labels = (
            ("postgraduate_degree", "Postgraduate degree"),
            ("bachelors_degree", "Bachelor's degree"),
            ("associates_degree", "Associate degree"),
            ("high_school", "High school"),
            ("professional_certification", "Professional certification"),
        )
        selected = [label for key, label in labels if value.get(key)]
        if selected:
            return ", ".join(selected)[:200]
        if value.get("degree_mentioned"):
            return "Degree mentioned"
        if value.get("degree_preferred"):
            return "Degree preferred"
        return None


async def scrape_jsearch(max_pages: int | None = None) -> list[dict]:
    return await JSearchScraper(max_pages).scrape()