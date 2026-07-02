"""
Ingestion pipeline — normalizes identity, upserts stable source records,
writes snapshots, and classifies new listings as original/parallel/repost.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Company,
    EventType,
    JobEmbedding,
    JobEvent,
    JobPosting,
    JobSkill,
    JobSnapshot,
    JobSourceSighting,
)
from app.services.normalizer import enrich_job_identity, normalize_company_name
from app.services.repost_detector import RepostDetectionService, embed_text

log = structlog.get_logger()
repost_service = RepostDetectionService()


def _desc_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _stable_value(value):
    return value if value not in ("", [], {}) else None


def prepare_job_dict(raw_job_dict: dict) -> dict:
    """Copy and centrally recompute identity fields for every source."""
    job_dict = dict(raw_job_dict)
    job_dict["external_id"] = _stable_value(job_dict.get("external_id"))
    job_dict["source_url"] = _stable_value(job_dict.get("source_url"))
    job_dict.setdefault("employment_type", "Full-time")
    job_dict.setdefault("country", "US")
    return enrich_job_identity(job_dict)


async def get_or_create_company(name: str, db: AsyncSession) -> Company:
    name_normalized = normalize_company_name(name)
    result = await db.execute(
        select(Company).where(Company.name_normalized == name_normalized)
    )
    company = result.scalar_one_or_none()
    if not company:
        company = Company(name=name.strip(), name_normalized=name_normalized)
        db.add(company)
        await db.flush()
        log.info("company_created", name=name)
    return company


async def _find_existing(job_dict: dict, db: AsyncSession) -> JobPosting | None:
    """
    Match only a stable source record.

    Identity-key-only matching was intentionally removed: two different
    external IDs posted together must remain separate parallel listings.
    """
    source = job_dict["source"]
    external_id = job_dict.get("external_id")
    source_url = job_dict.get("source_url")

    if external_id:
        result = await db.execute(
            select(JobPosting)
            .where(
                JobPosting.source == source,
                JobPosting.external_id == external_id,
            )
            .order_by(JobPosting.id.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    if source_url:
        result = await db.execute(
            select(JobPosting)
            .where(
                JobPosting.source == source,
                JobPosting.source_url == source_url,
            )
            .order_by(JobPosting.id.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    # Some feeds do not provide a stable ID. Reuse a very recent identical
    # source record rather than inserting it repeatedly every scrape cycle.
    if not external_id and not source_url:
        recent_cutoff = datetime.utcnow() - timedelta(days=2)
        result = await db.execute(
            select(JobPosting)
            .where(
                JobPosting.source == source,
                JobPosting.job_identity_key == job_dict["job_identity_key"],
                JobPosting.date_last_seen >= recent_cutoff,
            )
            .order_by(JobPosting.date_last_seen.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    return None


async def _upsert_source_sighting(
    job: JobPosting,
    job_dict: dict,
    db: AsyncSession,
    now: datetime,
) -> None:
    result = await db.execute(
        select(JobSourceSighting).where(
            JobSourceSighting.job_posting_id == job.id,
            JobSourceSighting.source == job_dict["source"],
        )
    )
    sighting = result.scalar_one_or_none()
    if sighting:
        sighting.last_seen = now
        sighting.source_url = job_dict.get("source_url") or sighting.source_url
        sighting.external_id = job_dict.get("external_id") or sighting.external_id
        sighting.applicant_count = job_dict.get("applicant_count")
    else:
        db.add(JobSourceSighting(
            job_posting_id=job.id,
            source=job_dict["source"],
            source_url=job_dict.get("source_url"),
            external_id=job_dict.get("external_id"),
            applicant_count=job_dict.get("applicant_count"),
            first_seen=now,
            last_seen=now,
        ))


async def _update_embedding(
    job: JobPosting,
    description: str,
    db: AsyncSession,
) -> None:
    if not description:
        return
    try:
        vector = embed_text(description[:2000])
        result = await db.execute(
            select(JobEmbedding).where(JobEmbedding.job_posting_id == job.id)
        )
        embedding = result.scalar_one_or_none()
        if embedding:
            embedding.vector = vector
            embedding.updated_at = datetime.utcnow()
        else:
            db.add(JobEmbedding(job_posting_id=job.id, vector=vector))
    except Exception as exc:
        log.warning("embedding_failed", job_id=job.id, error=str(exc))


async def _update_existing(
    existing: JobPosting,
    job_dict: dict,
    db: AsyncSession,
    now: datetime,
) -> tuple[JobPosting, bool]:
    old_applicants = existing.applicant_count
    old_desc = existing.description_raw or ""
    old_desc_hash = _desc_hash(old_desc)
    old_salary = (existing.salary_min, existing.salary_max)
    old_title = existing.title_raw

    new_desc = job_dict.get("description_raw") or old_desc
    new_desc_hash = _desc_hash(new_desc)

    # Identity fields are re-evaluated on every sighting so taxonomy upgrades
    # can correct previously stored records.
    existing.job_identity_key = job_dict["job_identity_key"]
    existing.identity_fingerprint = job_dict["identity_fingerprint"]
    existing.title_raw = job_dict.get("title_raw") or existing.title_raw
    existing.title_normalized = job_dict["title_normalized"]
    existing.job_family = job_dict.get("job_family")
    existing.specialization = job_dict.get("specialization")
    existing.title_parse_confidence = job_dict.get("title_parse_confidence")
    existing.seniority = job_dict.get("seniority") or existing.seniority
    existing.employment_type = job_dict.get("employment_type") or existing.employment_type

    for field in (
        "source_url", "location_raw", "city", "state", "country", "metro_area",
        "latitude", "longitude", "remote_type", "salary_min", "salary_max",
        "description_raw", "date_posted", "applicant_count",
    ):
        value = job_dict.get(field)
        if value is not None:
            setattr(existing, field, value)

    existing.salary_listed = bool(existing.salary_min or existing.salary_max)
    existing.date_last_seen = now
    existing.is_active = True

    db.add(JobSnapshot(
        job_posting_id=existing.id,
        snapshot_at=now,
        source=job_dict["source"],
        applicant_count=existing.applicant_count,
        description_raw=new_desc or None,
        description_hash=new_desc_hash,
        salary_min=existing.salary_min,
        salary_max=existing.salary_max,
        title_raw=existing.title_raw,
        is_active=True,
    ))

    if job_dict.get("applicant_count") is not None and old_applicants is not None:
        growth = job_dict["applicant_count"] - old_applicants
        if growth > 200:
            db.add(JobEvent(
                job_posting_id=existing.id,
                event_type=EventType.applicant_spike,
                source=job_dict["source"],
                payload={"old": old_applicants, "new": job_dict["applicant_count"], "growth": growth},
            ))

    if new_desc and new_desc_hash != old_desc_hash:
        db.add(JobEvent(
            job_posting_id=existing.id,
            event_type=EventType.description_changed,
            source=job_dict["source"],
            payload={"old_hash": old_desc_hash, "new_hash": new_desc_hash},
        ))
        await _update_embedding(existing, new_desc, db)

    if existing.title_raw != old_title:
        db.add(JobEvent(
            job_posting_id=existing.id,
            event_type=EventType.title_changed,
            source=job_dict["source"],
            payload={"old": old_title, "new": existing.title_raw},
        ))

    if (existing.salary_min, existing.salary_max) != old_salary:
        db.add(JobEvent(
            job_posting_id=existing.id,
            event_type=EventType.salary_changed,
            source=job_dict["source"],
            payload={"old": old_salary, "new": (existing.salary_min, existing.salary_max)},
        ))

    await _upsert_source_sighting(existing, job_dict, db, now)
    await db.flush()
    return existing, False


async def _create_new(
    job_dict: dict,
    db: AsyncSession,
    now: datetime,
) -> tuple[JobPosting, bool]:
    company = await get_or_create_company(job_dict["company_name"], db)

    job = JobPosting(
        company_id=company.id,
        job_identity_key=job_dict["job_identity_key"],
        identity_fingerprint=job_dict["identity_fingerprint"],
        listing_classification="original",
        external_id=job_dict.get("external_id"),
        source=job_dict["source"],
        source_url=job_dict.get("source_url"),
        title_raw=job_dict["title_raw"],
        title_normalized=job_dict["title_normalized"],
        job_family=job_dict.get("job_family"),
        specialization=job_dict.get("specialization"),
        title_parse_confidence=job_dict.get("title_parse_confidence"),
        location_raw=job_dict.get("location_raw"),
        city=job_dict.get("city"),
        state=job_dict.get("state"),
        country=job_dict.get("country", "US"),
        metro_area=job_dict.get("metro_area"),
        latitude=job_dict.get("latitude"),
        longitude=job_dict.get("longitude"),
        remote_type=job_dict.get("remote_type"),
        seniority=job_dict.get("seniority"),
        employment_type=job_dict.get("employment_type", "Full-time"),
        department=job_dict.get("department"),
        industry=job_dict.get("industry"),
        salary_min=job_dict.get("salary_min"),
        salary_max=job_dict.get("salary_max"),
        salary_currency=job_dict.get("salary_currency", "USD"),
        salary_listed=bool(job_dict.get("salary_min") or job_dict.get("salary_max")),
        description_raw=job_dict.get("description_raw"),
        date_posted=job_dict.get("date_posted"),
        date_first_seen=now,
        date_last_seen=now,
        is_active=True,
        days_active=0,
        applicant_count=job_dict.get("applicant_count"),
        repost_count=0,
    )
    db.add(job)
    await db.flush()

    for skill in job_dict.get("skills", []):
        db.add(JobSkill(
            job_posting_id=job.id,
            skill=skill["skill"],
            skill_normalized=skill["skill_normalized"],
            skill_category=skill.get("skill_category"),
        ))

    await _upsert_source_sighting(job, job_dict, db, now)

    description = job_dict.get("description_raw") or ""
    db.add(JobSnapshot(
        job_posting_id=job.id,
        snapshot_at=now,
        source=job_dict["source"],
        applicant_count=job_dict.get("applicant_count"),
        description_raw=description or None,
        description_hash=_desc_hash(description),
        salary_min=job_dict.get("salary_min"),
        salary_max=job_dict.get("salary_max"),
        title_raw=job_dict["title_raw"],
        is_active=True,
    ))

    db.add(JobEvent(
        job_posting_id=job.id,
        event_type=EventType.created,
        source=job_dict["source"],
        payload={
            "identity_key": job.job_identity_key,
            "identity_fingerprint": job.identity_fingerprint,
            "job_family": job.job_family,
            "specialization": job.specialization,
        },
    ))

    await _update_embedding(job, description, db)
    await db.flush()
    await repost_service.process_new_posting(job, db)
    return job, True


async def upsert_job(raw_job_dict: dict, db: AsyncSession) -> tuple[JobPosting, bool]:
    job_dict = prepare_job_dict(raw_job_dict)
    existing = await _find_existing(job_dict, db)
    now = datetime.utcnow()
    if existing:
        return await _update_existing(existing, job_dict, db, now)
    return await _create_new(job_dict, db, now)


async def ingest_jobs(jobs: list[dict], db: AsyncSession) -> dict:
    created = updated = errors = 0
    classifications = {"original": 0, "parallel": 0, "repost": 0}

    for raw_job_dict in jobs:
        try:
            # A bad record rolls back only its savepoint, not the full batch.
            async with db.begin_nested():
                job, is_new = await upsert_job(raw_job_dict, db)
                if is_new:
                    created += 1
                    classifications[job.listing_classification] = (
                        classifications.get(job.listing_classification, 0) + 1
                    )
                else:
                    updated += 1
        except Exception as exc:
            errors += 1
            log.error(
                "ingest_error",
                error=str(exc),
                title=raw_job_dict.get("title_raw", "?"),
                source=raw_job_dict.get("source", "?"),
            )

    await db.commit()
    return {
        "total": len(jobs),
        "created": created,
        "updated": updated,
        "errors": errors,
        "classifications": classifications,
    }
