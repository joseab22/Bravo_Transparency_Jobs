"""
Ingestion pipeline — upserts scraped jobs, writes snapshots, fires events.
"""
import hashlib
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.models.models import (
    Company, JobPosting, JobSkill, JobSourceSighting,
    JobSnapshot, JobEvent, JobEmbedding, EventType
)
from app.services.repost_detector import RepostDetectionService, embed_text
from app.services.normalizer import normalize_title

log = structlog.get_logger()
repost_service = RepostDetectionService()


def _desc_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:64] if text else ""


async def get_or_create_company(name: str, db: AsyncSession) -> Company:
    name_normalized = normalize_title(name)
    result = await db.execute(select(Company).where(Company.name_normalized == name_normalized))
    company = result.scalar_one_or_none()
    if not company:
        company = Company(name=name, name_normalized=name_normalized)
        db.add(company)
        await db.flush()
        log.info("company_created", name=name)
    return company


async def upsert_job(job_dict: dict, db: AsyncSession) -> tuple:
    external_id = job_dict.get("external_id")
    source = job_dict["source"]
    identity_key = job_dict["job_identity_key"]

    # Look up existing by external_id+source, then identity_key+source
    existing = None
    if external_id:
        r = await db.execute(
            select(JobPosting).where(
                JobPosting.external_id == external_id,
                JobPosting.source == source,
            )
        )
        existing = r.scalar_one_or_none()

    if not existing:
        r = await db.execute(
            select(JobPosting).where(
                JobPosting.job_identity_key == identity_key,
                JobPosting.source == source,
            )
        )
        existing = r.scalar_one_or_none()

    now = datetime.utcnow()

    if existing:
        old_applicants = existing.applicant_count
        old_desc_hash = _desc_hash(existing.description_raw or "")
        new_desc = job_dict.get("description_raw", "")
        new_desc_hash = _desc_hash(new_desc)

        existing.date_last_seen = now
        existing.is_active = True
        if job_dict.get("applicant_count"):
            existing.applicant_count = job_dict["applicant_count"]

        # Write snapshot (per spec: source, applicants, description, salary, date_seen)
        snapshot = JobSnapshot(
            job_posting_id=existing.id,
            snapshot_at=now,
            source=source,
            applicant_count=existing.applicant_count,
            description_raw=new_desc or None,
            description_hash=new_desc_hash,
            salary_min=existing.salary_min,
            salary_max=existing.salary_max,
            title_raw=existing.title_raw,
            is_active=True,
        )
        db.add(snapshot)

        # Fire events for notable changes
        if job_dict.get("applicant_count") and old_applicants:
            growth = job_dict["applicant_count"] - old_applicants
            if growth > 200:
                db.add(JobEvent(
                    job_posting_id=existing.id,
                    event_type=EventType.applicant_spike,
                    source=source,
                    payload={"old": old_applicants, "new": job_dict["applicant_count"], "growth": growth},
                ))

        if new_desc and new_desc_hash != old_desc_hash:
            db.add(JobEvent(
                job_posting_id=existing.id,
                event_type=EventType.description_changed,
                source=source,
                payload={"old_hash": old_desc_hash, "new_hash": new_desc_hash},
            ))

        await db.flush()
        return existing, False

    # --- Create new posting ---
    company = await get_or_create_company(job_dict["company_name"], db)

    job = JobPosting(
        company_id=company.id,
        job_identity_key=identity_key,
        external_id=external_id,
        source=source,
        source_url=job_dict.get("source_url"),
        title_raw=job_dict["title_raw"],
        title_normalized=job_dict["title_normalized"],
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
        salary_min=job_dict.get("salary_min"),
        salary_max=job_dict.get("salary_max"),
        salary_listed=job_dict.get("salary_listed", False),
        description_raw=job_dict.get("description_raw"),
        date_posted=job_dict.get("date_posted"),
        date_first_seen=now,
        date_last_seen=now,
        is_active=True,
        days_active=0,
        repost_count=0,
    )
    db.add(job)
    await db.flush()

    # Skills
    for sd in job_dict.get("skills", []):
        db.add(JobSkill(
            job_posting_id=job.id,
            skill=sd["skill"],
            skill_normalized=sd["skill_normalized"],
            skill_category=sd.get("skill_category"),
        ))

    # Source sighting
    db.add(JobSourceSighting(
        job_posting_id=job.id,
        source=source,
        source_url=job_dict.get("source_url"),
        external_id=external_id,
    ))

    # Initial snapshot
    desc = job_dict.get("description_raw", "")
    db.add(JobSnapshot(
        job_posting_id=job.id,
        snapshot_at=now,
        source=source,
        applicant_count=job_dict.get("applicant_count"),
        description_raw=desc or None,
        description_hash=_desc_hash(desc),
        salary_min=job_dict.get("salary_min"),
        salary_max=job_dict.get("salary_max"),
        title_raw=job_dict["title_raw"],
        is_active=True,
    ))

    # Created event
    db.add(JobEvent(
        job_posting_id=job.id,
        event_type=EventType.created,
        source=source,
        payload={"identity_key": identity_key},
    ))

    # Embedding (standalone table per spec)
    desc_text = job_dict.get("description_raw", "")
    if desc_text:
        try:
            vector = embed_text(desc_text[:1000])
            db.add(JobEmbedding(
                job_posting_id=job.id,
                vector=vector,
            ))
        except Exception as e:
            log.warning("embedding_failed", job_id=job.id, error=str(e))

    await db.flush()
    await repost_service.process_new_posting(job, db)
    return job, True


async def ingest_jobs(jobs: list[dict], db: AsyncSession) -> dict:
    created = updated = errors = 0
    for job_dict in jobs:
        try:
            _, is_new = await upsert_job(job_dict, db)
            if is_new:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors += 1
            log.error("ingest_error", error=str(e), title=job_dict.get("title_raw", "?"))

    await db.commit()
    return {"total": len(jobs), "created": created, "updated": updated, "errors": errors}
