"""Cached, opt-in location enrichment for unique location strings.

Collection never geocodes individual postings. This task processes a small
batch of unique locations, caches provider results, and applies each result to
all matching jobs.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utc_now
from app.models.models import JobPosting, LocationCache
from app.services.normalizer import normalize_location_text

log = structlog.get_logger()


def _key(value: str) -> str:
    return (normalize_location_text(value) or "").lower()


def _geocode(value: str):
    """Run the configured provider in a worker thread."""
    if settings.geocoding_provider == "google":
        from geopy.geocoders import GoogleV3

        geocoder = GoogleV3(api_key=settings.google_geocoding_api_key, timeout=15)
    else:
        from geopy.geocoders import Nominatim

        geocoder = Nominatim(
            user_agent="JobLens/1.0 hiring-transparency-research",
            timeout=15,
        )
    return geocoder.geocode(value, exactly_one=True)


def _address_components(location: Any) -> tuple[str | None, str | None, str | None]:
    """Return city, state, country for Nominatim or Google geopy results."""
    raw = location.raw if isinstance(getattr(location, "raw", None), dict) else {}
    address = raw.get("address")
    if isinstance(address, dict):
        city = address.get("city") or address.get("town") or address.get("village") or address.get("county")
        state = address.get("state") or address.get("state_code")
        country = address.get("country_code")
        return city, state, country.upper() if isinstance(country, str) else None

    values: dict[str, str] = {}
    for item in raw.get("address_components", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        short = item.get("short_name") or item.get("long_name")
        for kind in item.get("types", []):
            if short:
                values[kind] = short
    city = (
        values.get("locality")
        or values.get("postal_town")
        or values.get("administrative_area_level_2")
    )
    state = values.get("administrative_area_level_1")
    country = values.get("country")
    return city, state, country


async def enrich_locations(db: AsyncSession, limit: int | None = None) -> dict:
    if not settings.geocoding_enabled:
        return {"status": "disabled", "updated_jobs": 0, "requests": 0}

    batch = limit or settings.geocoding_batch_size
    rows = await db.execute(
        select(JobPosting.location_raw)
        .where(
            JobPosting.location_raw.is_not(None),
            JobPosting.latitude.is_(None),
            or_(JobPosting.remote_type.is_(None), JobPosting.remote_type != "Remote"),
        )
        .distinct()
        .limit(batch * 5)
    )

    unique: list[str] = []
    seen_keys: set[str] = set()
    for (value,) in rows.all():
        if not value or "|" in value or ";" in value:
            continue
        key = _key(value)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(value)
        if len(unique) >= batch:
            break

    requests = updated_jobs = cache_hits = 0
    cooldown = utc_now() - timedelta(hours=settings.geocoding_retry_hours)

    for raw in unique:
        key = _key(raw)
        cached = await db.scalar(select(LocationCache).where(LocationCache.location_key == key))

        if cached and cached.status == "success":
            cache_hits += 1
        elif cached and cached.status == "failed" and cached.last_attempt_at and cached.last_attempt_at > cooldown:
            continue
        else:
            cached = cached or LocationCache(
                location_key=key,
                location_raw=raw,
                provider=settings.geocoding_provider,
            )
            if cached.id is None:
                db.add(cached)
                await db.flush()

            try:
                requests += 1
                location = await asyncio.to_thread(_geocode, raw)
                cached.attempt_count = (cached.attempt_count or 0) + 1
                cached.last_attempt_at = utc_now()
                cached.provider = settings.geocoding_provider

                if not location:
                    cached.status = "failed"
                    cached.last_error = "No match"
                    await db.commit()
                    await asyncio.sleep(settings.geocoding_delay_seconds)
                    continue

                city, state, country = _address_components(location)
                cached.status = "success"
                cached.latitude = float(location.latitude)
                cached.longitude = float(location.longitude)
                cached.city = city
                cached.state = state
                cached.country = country or "US"
                cached.metro_area = ", ".join(x for x in (city, state) if x) or raw
                cached.last_error = None
            except Exception as exc:
                cached.status = "failed"
                cached.last_error = str(exc)[:1000]
                cached.attempt_count = (cached.attempt_count or 0) + 1
                cached.last_attempt_at = utc_now()
                log.warning("geocode_failed", location=raw, provider=settings.geocoding_provider, error=str(exc))

            await db.commit()
            await asyncio.sleep(settings.geocoding_delay_seconds)

        if cached.status == "success":
            result = await db.execute(
                update(JobPosting)
                .where(JobPosting.location_raw == raw)
                .values(
                    city=cached.city,
                    state=cached.state,
                    country=cached.country,
                    metro_area=cached.metro_area,
                    latitude=cached.latitude,
                    longitude=cached.longitude,
                    active_hiring_confidence=None,
                )
            )
            updated_jobs += result.rowcount or 0
            await db.commit()

    return {
        "status": "completed",
        "unique_locations": len(unique),
        "requests": requests,
        "cache_hits": cache_hits,
        "updated_jobs": updated_jobs,
    }
