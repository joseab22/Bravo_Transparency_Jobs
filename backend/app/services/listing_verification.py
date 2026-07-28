"""Conservative direct-URL availability checks for job listings.

A listing is only considered inactive when the response is conclusive. Access
blocks, rate limits, CAPTCHAs, timeouts, login redirects, and server failures
remain unknown so JobLens does not remove potentially live jobs by mistake.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import urlparse

import httpx


INACTIVE_STATUS_CODES = {404, 410}
BLOCKED_OR_UNKNOWN_STATUS_CODES = {401, 403, 407, 423, 425, 429, 451, 999}

# These phrases are intentionally strong. Avoid vague phrases such as
# "not available" because they can appear in unrelated page content.
INACTIVE_MARKERS: tuple[tuple[str, str], ...] = (
    ("no_longer_accepting", r"\bno longer accepting applications\b"),
    ("job_no_longer_available", r"\b(?:this |the )?job (?:is )?no longer available\b"),
    ("position_no_longer_available", r"\b(?:this |the )?position (?:is )?no longer available\b"),
    ("posting_expired", r"\b(?:this |the )?(?:job )?posting (?:has )?expired\b"),
    ("job_expired", r"\b(?:this |the )?job (?:has )?expired\b"),
    ("position_filled", r"\b(?:this |the )?position (?:has been|is) filled\b"),
    ("role_filled", r"\b(?:this |the )?role (?:has been|is) filled\b"),
    ("job_closed", r"\b(?:this |the )?job (?:has been|is) closed\b"),
    ("posting_closed", r"\b(?:this |the )?posting (?:has been|is) closed\b"),
    ("job_not_found", r"\bjob (?:was )?not found\b"),
    ("opening_not_found", r"\bopening (?:was )?not found\b"),
    ("position_removed", r"\b(?:this |the )?position (?:has been|was) removed\b"),
    ("opportunity_unavailable", r"\b(?:this )?opportunity is no longer available\b"),
    ("workday_expired", r"\bjob posting you(?:'|’)re looking for has expired\b"),
)

BLOCKED_MARKERS: tuple[tuple[str, str], ...] = (
    ("captcha", r"\b(?:captcha|recaptcha)\b"),
    ("verify_human", r"\bverify (?:that )?you are (?:a )?human\b"),
    ("access_denied", r"\baccess denied\b"),
    ("request_blocked", r"\b(?:your )?request (?:has been|was) blocked\b"),
    ("bot_detection", r"\b(?:unusual traffic|automated requests|bot detection)\b"),
    ("cloudflare_challenge", r"\b(?:cloudflare ray id|checking your browser)\b"),
    ("enable_cookies", r"\benable javascript and cookies to continue\b"),
)

GENERIC_REDIRECT_PATHS = {
    "", "/", "/login", "/signin", "/sign-in", "/jobs", "/jobs/", "/jobs/search",
    "/careers", "/careers/", "/search", "/search/",
}


@dataclass(slots=True)
class URLCheckResult:
    url: str
    outcome: str  # active, inactive, or unknown
    reason: str
    status_code: int | None = None
    final_url: str | None = None
    marker: str | None = None
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class JobCheckResult:
    job_id: int
    outcome: str
    reason: str
    urls: list[URLCheckResult]

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "outcome": self.outcome,
            "reason": self.reason,
            "urls": [item.as_dict() for item in self.urls],
        }


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _first_marker(text: str, markers: Iterable[tuple[str, str]]) -> str | None:
    for name, pattern in markers:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return name
    return None


def classify_page(
    *,
    original_url: str,
    final_url: str,
    status_code: int,
    text: str,
    redirected: bool,
) -> URLCheckResult:
    """Classify an HTTP response without making uncertain failures destructive."""
    if status_code in INACTIVE_STATUS_CODES:
        return URLCheckResult(
            url=original_url,
            outcome="inactive",
            reason=f"HTTP {status_code} means the listing page is gone.",
            status_code=status_code,
            final_url=final_url,
        )

    if status_code in BLOCKED_OR_UNKNOWN_STATUS_CODES:
        return URLCheckResult(
            url=original_url,
            outcome="unknown",
            reason=f"HTTP {status_code} prevented a reliable availability check.",
            status_code=status_code,
            final_url=final_url,
        )

    if status_code >= 500:
        return URLCheckResult(
            url=original_url,
            outcome="unknown",
            reason=f"The site returned HTTP {status_code}, which may be temporary.",
            status_code=status_code,
            final_url=final_url,
        )

    if status_code >= 400:
        return URLCheckResult(
            url=original_url,
            outcome="unknown",
            reason=f"HTTP {status_code} is not conclusive enough to remove the listing.",
            status_code=status_code,
            final_url=final_url,
        )

    compact = _compact_text(text)
    inactive_marker = _first_marker(compact, INACTIVE_MARKERS)
    if inactive_marker:
        return URLCheckResult(
            url=original_url,
            outcome="inactive",
            reason="The page explicitly says the listing is closed, expired, filled, or unavailable.",
            status_code=status_code,
            final_url=final_url,
            marker=inactive_marker,
        )

    blocked_marker = _first_marker(compact, BLOCKED_MARKERS)
    if blocked_marker:
        return URLCheckResult(
            url=original_url,
            outcome="unknown",
            reason="The site displayed an access challenge instead of the listing.",
            status_code=status_code,
            final_url=final_url,
            marker=blocked_marker,
        )

    original = urlparse(original_url)
    final = urlparse(final_url)
    final_path = (final.path or "").lower()
    if redirected and final_path in GENERIC_REDIRECT_PATHS:
        return URLCheckResult(
            url=original_url,
            outcome="unknown",
            reason="The listing redirected to a generic home, search, careers, or login page.",
            status_code=status_code,
            final_url=final_url,
        )

    if redirected and original.hostname != final.hostname and final_path in GENERIC_REDIRECT_PATHS:
        return URLCheckResult(
            url=original_url,
            outcome="unknown",
            reason="The listing redirected to another site's generic page.",
            status_code=status_code,
            final_url=final_url,
        )

    return URLCheckResult(
        url=original_url,
        outcome="active",
        reason="The page loaded successfully and did not show a conclusive closed-listing message.",
        status_code=status_code,
        final_url=final_url,
    )


def combine_url_results(job_id: int, results: list[URLCheckResult]) -> JobCheckResult:
    """Keep a job active when any known source remains active.

    A job is deactivated only when every checked URL is conclusively inactive.
    Any blocked or uncertain URL prevents automatic deactivation.
    """
    if not results:
        return JobCheckResult(job_id, "unknown", "No usable HTTP or HTTPS URL was available.", [])

    if any(item.outcome == "active" for item in results):
        return JobCheckResult(
            job_id,
            "active",
            "At least one known listing URL is still available.",
            results,
        )

    if all(item.outcome == "inactive" for item in results):
        return JobCheckResult(
            job_id,
            "inactive",
            "Every known listing URL gave a conclusive closed result.",
            results,
        )

    return JobCheckResult(
        job_id,
        "unknown",
        "No URL was confirmed active, but at least one result was blocked or inconclusive.",
        results,
    )


class ListingAvailabilityVerifier:
    """Rate-limited, cached, asynchronous URL verifier."""

    def __init__(
        self,
        *,
        concurrency: int = 6,
        request_timeout: float = 20.0,
        attempts: int = 2,
        per_domain_delay: float = 1.0,
        max_body_bytes: int = 262_144,
    ) -> None:
        self.concurrency = max(1, concurrency)
        self.request_timeout = request_timeout
        self.attempts = max(1, attempts)
        self.per_domain_delay = max(0.0, per_domain_delay)
        self.max_body_bytes = max(16_384, max_body_bytes)
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._domain_last_request: dict[str, float] = {}
        self._cache: dict[str, asyncio.Task[URLCheckResult]] = {}
        self._cache_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout),
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36 JobLensAvailabilityCheck/1.0"
                ),
            },
        )

    async def __aenter__(self) -> "ListingAvailabilityVerifier":
        return self

    async def __aexit__(self, *_args) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def verify_url(self, url: str) -> URLCheckResult:
        clean = (url or "").strip()
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return URLCheckResult(
                url=clean,
                outcome="unknown",
                reason="The URL is missing or is not an HTTP/HTTPS address.",
            )

        async with self._cache_lock:
            task = self._cache.get(clean)
            if task is None:
                task = asyncio.create_task(self._verify_url_uncached(clean))
                self._cache[clean] = task
        return await task

    async def verify_job(self, job_id: int, urls: Iterable[str | None]) -> JobCheckResult:
        unique_urls: list[str] = []
        seen: set[str] = set()
        for value in urls:
            clean = (value or "").strip()
            if clean and clean not in seen:
                unique_urls.append(clean)
                seen.add(clean)
        results = await asyncio.gather(*(self.verify_url(url) for url in unique_urls))
        return combine_url_results(job_id, list(results))

    async def _wait_for_domain(self, hostname: str) -> None:
        lock = self._domain_locks.setdefault(hostname, asyncio.Lock())
        await lock.acquire()
        last = self._domain_last_request.get(hostname)
        if last is not None:
            remaining = self.per_domain_delay - (time.monotonic() - last)
            if remaining > 0:
                await asyncio.sleep(remaining)

    def _release_domain(self, hostname: str) -> None:
        self._domain_last_request[hostname] = time.monotonic()
        self._domain_locks[hostname].release()

    async def _verify_url_uncached(self, url: str) -> URLCheckResult:
        hostname = (urlparse(url).hostname or "").lower()
        async with self._semaphore:
            for attempt in range(1, self.attempts + 1):
                await self._wait_for_domain(hostname)
                try:
                    result = await self._request_once(url)
                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                    result = URLCheckResult(
                        url=url,
                        outcome="unknown",
                        reason="A network error prevented a reliable check.",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                except Exception as exc:  # Keep a single bad URL from stopping the batch.
                    result = URLCheckResult(
                        url=url,
                        outcome="unknown",
                        reason="An unexpected error prevented a reliable check.",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                finally:
                    self._release_domain(hostname)

                retryable = result.status_code in {408, 425, 429, 500, 502, 503, 504}
                retryable = retryable or result.error is not None
                if not retryable or attempt == self.attempts:
                    return result
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

        return URLCheckResult(url=url, outcome="unknown", reason="The check did not complete.")

    async def _request_once(self, url: str) -> URLCheckResult:
        async with self._client.stream("GET", url) as response:
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                remaining = self.max_body_bytes - size
                if remaining <= 0:
                    break
                chunks.append(chunk[:remaining])
                size += min(len(chunk), remaining)
                if size >= self.max_body_bytes:
                    break

            body = b"".join(chunks)
            encoding = response.encoding or "utf-8"
            try:
                text = body.decode(encoding, errors="ignore")
            except LookupError:
                text = body.decode("utf-8", errors="ignore")

            final_url = str(response.url)
            return classify_page(
                original_url=url,
                final_url=final_url,
                status_code=response.status_code,
                text=text,
                redirected=bool(response.history),
            )
