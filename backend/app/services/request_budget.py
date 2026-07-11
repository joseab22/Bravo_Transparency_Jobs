"""Shared RapidAPI/JSearch request-budget enforcement.

The application reserves one unit before every HTTP attempt, including retries.
Redis makes the limit global across worker processes. RapidAPI response headers
are also persisted so the application stops while a provider-side reserve still
remains, protecting against overage charges and manual requests made elsewhere.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Mapping, Optional

from redis.asyncio import Redis


class RequestBudgetExceeded(RuntimeError):
    """Raised before a request when the configured budget is exhausted."""


@dataclass(frozen=True)
class RequestBudgetStatus:
    namespace: str
    monthly_limit: int
    reserve: int
    application_budget: int
    local_used: int
    local_remaining: int
    provider_limit: Optional[int]
    provider_remaining: Optional[int]
    reset_at_epoch: Optional[int]

    def as_dict(self) -> dict:
        return asdict(self)


_RESERVE_SCRIPT = """
local reset_at = tonumber(redis.call('HGET', KEYS[1], 'reset_at') or '0')
local now = tonumber(ARGV[1])
if reset_at > 0 and now >= reset_at then
    redis.call('DEL', KEYS[1])
end

local provider_remaining = redis.call('HGET', KEYS[1], 'provider_remaining')
local reserve = tonumber(ARGV[3])
if provider_remaining and tonumber(provider_remaining) <= reserve then
    return -2
end

local used = redis.call('HINCRBY', KEYS[1], 'local_used', 1)
local application_budget = tonumber(ARGV[2])
if used > application_budget then
    redis.call('HINCRBY', KEYS[1], 'local_used', -1)
    return -1
end

if provider_remaining then
    redis.call('HINCRBY', KEYS[1], 'provider_remaining', -1)
end
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
return used
"""


class RapidAPIRequestBudget:
    """Redis-backed request counter with provider-header reconciliation."""

    def __init__(
        self,
        redis_url: str,
        *,
        namespace: str,
        monthly_limit: int,
        reserve: int,
    ) -> None:
        self.namespace = namespace
        self.monthly_limit = monthly_limit
        self.reserve = reserve
        self.application_budget = monthly_limit - reserve
        self.key = f"joblens:request-budget:{namespace}"
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def close(self) -> None:
        await self._redis.aclose()

    async def reserve_request(self) -> int:
        """Atomically reserve one request attempt or raise before sending it."""
        result = int(await self._redis.eval(
            _RESERVE_SCRIPT,
            1,
            self.key,
            int(time.time()),
            self.application_budget,
            self.reserve,
            45 * 24 * 60 * 60,
        ))
        if result == -1:
            raise RequestBudgetExceeded(
                f"{self.namespace} application budget reached "
                f"({self.application_budget}/{self.monthly_limit}); "
                f"{self.reserve} requests remain reserved"
            )
        if result == -2:
            raise RequestBudgetExceeded(
                f"{self.namespace} provider-reported remaining quota reached "
                f"the {self.reserve}-request reserve"
            )
        return result

    async def update_from_headers(self, headers: Mapping[str, str]) -> None:
        """Store RapidAPI quota headers after every response, successful or not."""
        limit = _to_int(headers.get("x-ratelimit-requests-limit"))
        remaining = _to_int(headers.get("x-ratelimit-requests-remaining"))
        reset_seconds = _to_int(headers.get("x-ratelimit-requests-reset"))
        if limit is None and remaining is None and reset_seconds is None:
            return

        values: dict[str, int] = {}
        if limit is not None:
            values["provider_limit"] = limit
        if remaining is not None:
            values["provider_remaining"] = remaining
        if reset_seconds is not None:
            values["reset_at"] = int(time.time()) + max(reset_seconds, 0)

        if values:
            await self._redis.hset(self.key, mapping=values)
            ttl = max((values.get("reset_at", 0) - int(time.time())) + 86_400, 86_400)
            await self._redis.expire(self.key, ttl)

    async def status(self) -> RequestBudgetStatus:
        data = await self._redis.hgetall(self.key)
        reset_at = _to_int(data.get("reset_at"))
        if reset_at is not None and int(time.time()) >= reset_at:
            await self._redis.delete(self.key)
            data = {}
            reset_at = None

        local_used = _to_int(data.get("local_used")) or 0
        return RequestBudgetStatus(
            namespace=self.namespace,
            monthly_limit=self.monthly_limit,
            reserve=self.reserve,
            application_budget=self.application_budget,
            local_used=local_used,
            local_remaining=max(self.application_budget - local_used, 0),
            provider_limit=_to_int(data.get("provider_limit")),
            provider_remaining=_to_int(data.get("provider_remaining")),
            reset_at_epoch=reset_at,
        )


def _to_int(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None
