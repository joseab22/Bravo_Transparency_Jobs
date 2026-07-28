"""Aggregate publisher evidence across canonical job groups."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from types import SimpleNamespace
from typing import Iterable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.time import utc_now
from app.models.models import JobPosting

_SOURCE_PRIORITY = {
    "company_site": 0,
    "company-site": 0,
    "linkedin": 10,
    "indeed": 20,
    "glassdoor": 30,
    "ziprecruiter": 40,
    "dice": 50,
    "monster": 60,
    "jobright": 70,
    "simplify": 80,
    "jsearch": 90,
}


def canonical_group_id(job: JobPosting) -> int:
    return job.canonical_job_id or job.id


async def load_canonical_sources(
    jobs: Iterable[JobPosting],
    db: AsyncSession,
    *,
    max_age_days: int | None = None,
) -> dict[int, list[dict]]:
    """Return publisher evidence from active canonical members in the requested age window."""
    group_ids = {canonical_group_id(job) for job in jobs}
    if not group_ids:
        return {}

    group_expr = func.coalesce(JobPosting.canonical_job_id, JobPosting.id)
    conditions = [
        group_expr.in_(group_ids),
        JobPosting.is_active.is_(True),
    ]
    if max_age_days is not None:
        cutoff = utc_now() - timedelta(days=max_age_days)
        conditions.append(or_(
            JobPosting.date_posted >= cutoff,
            and_(
                JobPosting.date_posted.is_(None),
                JobPosting.date_first_seen >= cutoff,
            ),
        ))

    members = list((await db.execute(
        select(JobPosting)
        .options(selectinload(JobPosting.source_sightings))
        .where(*conditions)
    )).scalars().unique())

    aggregated: dict[int, dict[str, dict]] = defaultdict(dict)
    for member in members:
        group_id = canonical_group_id(member)

        sightings = list(member.source_sightings)
        if not sightings:
            # Legacy rows created before source sightings were introduced still
            # expose their primary board instead of returning an empty source list.
            sightings = [SimpleNamespace(
                source=member.source,
                publisher_name=member.publisher_name,
                collection_provider=member.collection_provider,
                source_url=member.source_url,
                external_id=member.external_id,
                sighting_key=f"legacy-{member.id}-{member.source}",
                is_direct=False,
                first_seen=member.date_first_seen,
                last_seen=member.date_last_seen,
            )]

        for sighting in sightings:
            original_key = getattr(sighting, "sighting_key", None) or f"{sighting.source}|{sighting.source_url or ''}"
            # The same apply URL may be discovered under different provider IDs
            # or canonical member rows. Collapse that exact link while keeping
            # different URLs from the same publisher separate.
            aggregation_key = (
                f"{sighting.source}|{sighting.source_url}"
                if sighting.source_url
                else original_key
            )
            current = aggregated[group_id].get(aggregation_key)
            candidate = {
                "sighting_key": original_key,
                "source": sighting.source,
                "publisher_name": sighting.publisher_name or sighting.source.replace("-", " ").title(),
                "collection_provider": sighting.collection_provider,
                "source_url": sighting.source_url,
                "external_id": sighting.external_id,
                "is_direct": bool(getattr(sighting, "is_direct", False)),
                "first_seen": sighting.first_seen,
                "last_seen": sighting.last_seen,
                "is_active": member.is_active,
                "listing_ids": [member.id],
            }
            if current is None:
                aggregated[group_id][aggregation_key] = candidate
                continue

            current["first_seen"] = min(current["first_seen"], sighting.first_seen)
            current["last_seen"] = max(current["last_seen"], sighting.last_seen)
            current["is_active"] = current["is_active"] or member.is_active
            current["listing_ids"] = sorted(set([*current["listing_ids"], member.id]))
            if member.is_active or not current.get("source_url"):
                current["source_url"] = sighting.source_url or current.get("source_url")
                current["external_id"] = sighting.external_id or current.get("external_id")
                current["publisher_name"] = sighting.publisher_name or current["publisher_name"]
                current["collection_provider"] = sighting.collection_provider or current.get("collection_provider")
                current["is_direct"] = current["is_direct"] or bool(getattr(sighting, "is_direct", False))

    return {
        group_id: sorted(
            values.values(),
            key=lambda item: (
                _SOURCE_PRIORITY.get(item["source"], 100),
                item["publisher_name"].lower(),
            ),
        )
        for group_id, values in aggregated.items()
    }


def own_sources(job: JobPosting) -> list[dict]:
    """Return only this row's own publisher sightings — not the wider canonical group."""
    sightings = list(job.source_sightings)
    if not sightings:
        sightings = [SimpleNamespace(
            source=job.source,
            publisher_name=job.publisher_name,
            collection_provider=job.collection_provider,
            source_url=job.source_url,
            external_id=job.external_id,
            sighting_key=f"legacy-{job.id}-{job.source}",
            is_direct=False,
            first_seen=job.date_first_seen,
            last_seen=job.date_last_seen,
        )]

    deduped: dict[str, dict] = {}
    for sighting in sightings:
        key = f"{sighting.source}|{sighting.source_url}" if sighting.source_url else (
            getattr(sighting, "sighting_key", None) or f"{sighting.source}|"
        )
        deduped[key] = {
            "sighting_key": getattr(sighting, "sighting_key", None) or key,
            "source": sighting.source,
            "publisher_name": sighting.publisher_name or sighting.source.replace("-", " ").title(),
            "collection_provider": sighting.collection_provider,
            "source_url": sighting.source_url,
            "external_id": sighting.external_id,
            "is_direct": bool(getattr(sighting, "is_direct", False)),
            "first_seen": sighting.first_seen,
            "last_seen": sighting.last_seen,
            "is_active": job.is_active,
            "listing_ids": [job.id],
        }

    return sorted(
        deduped.values(),
        key=lambda item: (_SOURCE_PRIORITY.get(item["source"], 100), item["publisher_name"].lower()),
    )