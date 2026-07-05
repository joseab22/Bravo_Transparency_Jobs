"""Shared, rate-limit-aware HTTP adapter for job sources."""
from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()


class ScraperRequestError(RuntimeError):
    pass


class ScraperRateLimitError(ScraperRequestError):
    pass


class BaseScraperAdapter(ABC):
    source_name = ""
    default_headers = {
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "JobLens/1.0 hiring-transparency-research",
    }
    retryable_status_codes = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        max_pages: Optional[int] = None,
        *,
        request_timeout: float = 30.0,
        max_request_attempts: int = 5,
        minimum_delay: float = 1.5,
        maximum_delay: float = 3.5,
        max_records: Optional[int] = None,
    ):
        self.max_pages = max_pages or settings.max_pages_per_source
        self.request_timeout = request_timeout
        self.max_request_attempts = max_request_attempts
        self.minimum_delay = minimum_delay
        self.maximum_delay = maximum_delay
        self.max_records = max_records
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        await self._get_client()
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.default_headers,
                timeout=self.request_timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def fetch_jobs(self, query: str, page: int = 1) -> dict | list:
        raise NotImplementedError

    @abstractmethod
    def parse_job(self, raw: dict) -> Optional[dict]:
        raise NotImplementedError

    async def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> dict | list:
        client = await self._get_client()
        for attempt in range(1, self.max_request_attempts + 1):
            try:
                response = await client.request(method, url, headers=headers, params=params, json=json)
                if response.status_code in self.retryable_status_codes:
                    delay = self._retry_delay(response, attempt)
                    event = "scraper_rate_limited" if response.status_code == 429 else "scraper_temporary_http_error"
                    log.warning(event, source=self.source_name, status_code=response.status_code, attempt=attempt, retry_after_seconds=round(delay, 2))
                    if attempt == self.max_request_attempts:
                        if response.status_code == 429:
                            raise ScraperRateLimitError(f"{self.source_name} remained rate limited")
                        response.raise_for_status()
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as exc:
                    raise ScraperRequestError(f"{self.source_name} returned invalid JSON") from exc
            except ScraperRateLimitError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                if attempt == self.max_request_attempts:
                    raise ScraperRequestError(f"{self.source_name} network request failed: {exc}") from exc
                delay = self._exponential_delay(attempt)
                log.warning("scraper_network_retry", source=self.source_name, attempt=attempt, retry_after_seconds=round(delay, 2), error=str(exc))
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as exc:
                raise ScraperRequestError(f"{self.source_name} returned HTTP {exc.response.status_code}") from exc
        raise ScraperRequestError(f"{self.source_name} request failed")

    async def scrape(self, queries: Optional[list[str]] = None) -> list[dict]:
        all_jobs: list[dict] = []
        seen: set[str] = set()
        try:
            for query in (queries or self.default_queries()):
                for page in range(1, self.max_pages + 1):
                    try:
                        raw_jobs = self.extract_job_list(await self.fetch_jobs(query, page))
                        if not raw_jobs:
                            break
                        for raw in raw_jobs:
                            try:
                                parsed = self.parse_job(raw)
                            except Exception as exc:
                                log.warning("scraper_record_parse_error", source=self.source_name, error=str(exc))
                                continue
                            if not parsed:
                                continue
                            key = str(parsed.get("external_id") or parsed.get("source_url") or f"{parsed.get('company_name')}|{parsed.get('title_raw')}|{parsed.get('location_raw')}")
                            if key in seen:
                                continue
                            seen.add(key)
                            all_jobs.append(parsed)
                            if self.max_records and len(all_jobs) >= self.max_records:
                                log.info("scraper_record_cap_reached", source=self.source_name, total=len(all_jobs))
                                return all_jobs
                        await asyncio.sleep(random.uniform(self.minimum_delay, self.maximum_delay))
                    except ScraperRateLimitError as exc:
                        log.error("scraper_source_rate_limited", source=self.source_name, query=query, page=page, error=str(exc))
                        return all_jobs
                    except Exception as exc:
                        log.error("scraper_page_error", source=self.source_name, query=query, page=page, error=str(exc))
                        break
            log.info("scraper_complete", source=self.source_name, total=len(all_jobs))
            return all_jobs
        finally:
            await self.close()

    def extract_job_list(self, value: Any) -> list:
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ("data", "jobs", "results", "jobResults"):
                if isinstance(value.get(key), list):
                    return value[key]
        return []

    @staticmethod
    def _parse_retry_after(value: str) -> Optional[float]:
        try:
            return float(value)
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return max((dt - datetime.now(timezone.utc)).total_seconds(), 0.0)
            except (TypeError, ValueError, OverflowError):
                return None

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        raw = response.headers.get("Retry-After")
        parsed = self._parse_retry_after(raw) if raw else None
        return min(max(parsed, 1.0), 300.0) if parsed is not None else self._exponential_delay(attempt)

    @staticmethod
    def _exponential_delay(attempt: int) -> float:
        return min(2 ** (attempt - 1), 60) + random.uniform(0.5, 2.0)

    def default_queries(self) -> list[str]:
        return [
            "software engineer", "data analyst", "data engineer", "data scientist",
            "machine learning engineer", "product manager", "security engineer",
        ]
