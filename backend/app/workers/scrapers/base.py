"""
Shared scraper base class.

All HTTP-based source adapters use this class for:
- HTTP 429 handling
- Retry-After support
- exponential backoff with jitter
- retries for transient network and 5xx errors
- courtesy delays between pages and queries
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import httpx
import structlog

log = structlog.get_logger()


class ScraperRequestError(RuntimeError):
    """Raised when an upstream job source cannot be fetched."""


class ScraperRateLimitError(ScraperRequestError):
    """Raised when an upstream source continues returning HTTP 429."""


class BaseScraperAdapter(ABC):
    """Abstract base class for all job-source adapters."""

    source_name: str = ""

    default_headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "JobLens/1.0 (+job-market-research)",
    }

    retryable_status_codes = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        max_pages: int = 10,
        *,
        request_timeout: float = 30.0,
        max_request_attempts: int = 5,
        minimum_delay: float = 1.5,
        maximum_delay: float = 3.5,
    ):
        self.max_pages = max_pages
        self.request_timeout = request_timeout
        self.max_request_attempts = max_request_attempts
        self.minimum_delay = minimum_delay
        self.maximum_delay = maximum_delay

    @abstractmethod
    async def fetch_jobs(self, query: str, page: int = 1) -> dict | list:
        """Fetch raw data for a query and page."""

    @abstractmethod
    def parse_job(self, raw: dict) -> Optional[dict]:
        """Convert a raw source record to the normalized ingestion schema."""

    async def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> dict | list:
        """Make a rate-limit-aware HTTP request and return decoded JSON."""

        request_headers = dict(self.default_headers)
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None

        async with httpx.AsyncClient(
            headers=request_headers,
            timeout=self.request_timeout,
            follow_redirects=True,
        ) as client:
            for attempt in range(1, self.max_request_attempts + 1):
                try:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json,
                    )

                    if response.status_code == 429:
                        delay = self._retry_delay(response, attempt)
                        log.warning(
                            "scraper_rate_limited",
                            source=self.source_name,
                            url=url,
                            attempt=attempt,
                            max_attempts=self.max_request_attempts,
                            retry_after_seconds=round(delay, 2),
                        )
                        if attempt == self.max_request_attempts:
                            raise ScraperRateLimitError(
                                f"{self.source_name} remained rate limited after "
                                f"{self.max_request_attempts} attempts"
                            )
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code in self.retryable_status_codes:
                        delay = self._retry_delay(response, attempt)
                        log.warning(
                            "scraper_temporary_http_error",
                            source=self.source_name,
                            url=url,
                            status_code=response.status_code,
                            attempt=attempt,
                            retry_after_seconds=round(delay, 2),
                        )
                        if attempt == self.max_request_attempts:
                            response.raise_for_status()
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ScraperRequestError(
                            f"{self.source_name} returned invalid JSON"
                        ) from exc

                except ScraperRateLimitError:
                    raise
                except (
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ) as exc:
                    last_error = exc
                    if attempt == self.max_request_attempts:
                        break
                    delay = self._exponential_delay(attempt)
                    log.warning(
                        "scraper_network_retry",
                        source=self.source_name,
                        url=url,
                        attempt=attempt,
                        error=str(exc),
                        retry_after_seconds=round(delay, 2),
                    )
                    await asyncio.sleep(delay)
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    raise ScraperRequestError(
                        f"{self.source_name} returned HTTP "
                        f"{exc.response.status_code}"
                    ) from exc

        raise ScraperRequestError(
            f"{self.source_name} request failed after "
            f"{self.max_request_attempts} attempts: {last_error}"
        )

    async def scrape(self, queries: Optional[list[str]] = None) -> list[dict]:
        """Fetch and parse all configured queries and pages."""

        queries = queries or self.default_queries()
        all_jobs: list[dict] = []

        for query in queries:
            log.info("scraper_query_start", source=self.source_name, query=query)

            for page in range(1, self.max_pages + 1):
                try:
                    raw_response = await self.fetch_jobs(query, page)
                    raw_jobs = self.extract_job_list(raw_response)

                    if not raw_jobs:
                        log.info(
                            "scraper_no_more_results",
                            source=self.source_name,
                            query=query,
                            page=page,
                        )
                        break

                    for raw in raw_jobs:
                        parsed = self.parse_job(raw)
                        if parsed:
                            all_jobs.append(parsed)

                    await self.rate_limit_sleep()

                except ScraperRateLimitError as exc:
                    log.error(
                        "scraper_source_rate_limited",
                        source=self.source_name,
                        query=query,
                        page=page,
                        error=str(exc),
                    )
                    return all_jobs
                except Exception as exc:
                    log.error(
                        "scraper_page_error",
                        source=self.source_name,
                        query=query,
                        page=page,
                        error=str(exc),
                    )
                    break

        log.info("scraper_complete", source=self.source_name, total=len(all_jobs))
        return all_jobs

    def extract_job_list(self, raw_response: Any) -> list:
        if isinstance(raw_response, list):
            return raw_response
        if isinstance(raw_response, dict):
            return raw_response.get(
                "data",
                raw_response.get("jobs", raw_response.get("results", [])),
            )
        return []

    async def rate_limit_sleep(self) -> None:
        await asyncio.sleep(
            random.uniform(self.minimum_delay, self.maximum_delay)
        )

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            parsed = self._parse_retry_after(retry_after)
            if parsed is not None:
                return min(max(parsed, 1.0), 300.0)
        return self._exponential_delay(attempt)

    @staticmethod
    def _parse_retry_after(value: str) -> Optional[float]:
        try:
            return float(value)
        except ValueError:
            pass

        try:
            retry_datetime = parsedate_to_datetime(value)
            if retry_datetime.tzinfo is None:
                retry_datetime = retry_datetime.replace(tzinfo=timezone.utc)
            return max(
                (retry_datetime - datetime.now(timezone.utc)).total_seconds(),
                0.0,
            )
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _exponential_delay(attempt: int) -> float:
        base_delay = min(2 ** (attempt - 1), 60)
        return base_delay + random.uniform(0.5, 2.0)

    def default_queries(self) -> list[str]:
        return [
            "data analyst",
            "data engineer",
            "data scientist",
            "machine learning engineer",
            "software engineer",
            "analytics engineer",
            "business analyst",
        ]
