"""Aggregate publisher evidence across canonical job groups."""
from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    jobs: Iterable[JobPosting], db: AsyncSession
) -> dict[int, list[dict]]:
    """Return one combined publisher list for each canonical job group."""
    group_ids = {canonical_group_id(job) for job in jobs}
    if not group_ids:
        return {}

    group_expr = func.coalesce(JobPosting.canonical_job_id, JobPosting.id)
    members = list((await db.execute(
        select(JobPosting)
        .options(selectinload(JobPosting.source_sightings))
        .where(group_expr.in_(group_ids))
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
