"""Fast transactional ingestion.

Collection is intentionally separated from geocoding, embedding generation,
identity-history classification, and scoring so large feeds can commit safely.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.time import utc_now
from app.models.models import (
    Company, EventType, JobEvent, JobPosting, JobSkill,
    JobSnapshot, JobSourceSighting,
)
from app.services.normalizer import (
    calculate_days_active, normalize_company_name, normalize_source_url, prepare_job_record,
)
from app.services.repost_detector import SCORE_FIELDS

log = structlog.get_logger()


def _desc_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest() if text else ""


def _invalidate_scores(job: JobPosting) -> None:
    for field in SCORE_FIELDS:
        setattr(job, field, None)


def _chunks(values: list[Any], size: int = 900) -> Iterable[list[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


async def _prepare_company_cache(
    records: list[dict[str, Any]], db: AsyncSession
) -> dict[str, Company]:
    """Resolve each unique company once for the entire scrape run."""
    display_names: dict[str, str] = {}
    for record in records:
        normalized = normalize_company_name(record["company_name"])
        display_names.setdefault(normalized, record["company_name"])

    cache: dict[str, Company] = {}
    names = list(display_names)
    for chunk in _chunks(names):
        rows = await db.execute(select(Company).where(Company.name_normalized.in_(chunk)))
        for company in rows.scalars():
            cache[company.name_normalized] = company

    for record in records:
        normalized = normalize_company_name(record["company_name"])
        company = cache.get(normalized)
        if company and not company.website and record.get("company_website"):
            company.website = str(record["company_website"])[:500]
        if company and not company.industry and record.get("industry"):
            company.industry = str(record["industry"])[:100]

    for normalized, display in display_names.items():
        if normalized in cache:
            continue
        seed = next(record for record in records if normalize_company_name(record["company_name"]) == normalized)
        company = Company(
            name=display[:255],
            name_normalized=normalized[:255],
            website=(str(seed.get("company_website"))[:500] if seed.get("company_website") else None),
            industry=(str(seed.get("industry"))[:100] if seed.get("industry") else None),
        )
        try:
            async with db.begin_nested():
                db.add(company)
                await db.flush()
        except IntegrityError:
            # A concurrent ingestion run (a different source's scrape task)
            # created the same normalized company between our lookup above
            # and this insert. Use its row instead of failing the whole batch.
            result = await db.execute(
                select(Company).where(Company.name_normalized == normalized)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                raise
            company = existing
        cache[normalized] = company
    return cache


async def _prefetch_existing_jobs(
    records: list[dict[str, Any]],
    company_cache: dict[str, Company],
    db: AsyncSession,
) -> dict[str, dict[tuple[Any, ...], JobPosting]]:
    """Load stable-ID/URL matches in chunks before row-by-row ingestion."""
    external_by_source: dict[str, set[str]] = {}
    external_by_provider: dict[str, set[str]] = {}
    urls_by_source: dict[str, set[str]] = {}
    for record in records:
        source = record["source"]
        provider = record.get("collection_provider") or source
        if record.get("external_id") not in (None, ""):
            external_id = str(record["external_id"])
            external_by_source.setdefault(source, set()).add(external_id)
            external_by_provider.setdefault(provider, set()).add(external_id)
        if record.get("source_url"):
            urls_by_source.setdefault(source, set()).add(record["source_url"])

    options = (
        selectinload(JobPosting.snapshots),
        selectinload(JobPosting.source_sightings),
        selectinload(JobPosting.skills),
    )
    external: dict[tuple[Any, ...], JobPosting] = {}
    provider_external: dict[tuple[Any, ...], JobPosting] = {}
    urls: dict[tuple[Any, ...], JobPosting] = {}

    for source, identifiers in external_by_source.items():
        for chunk in _chunks(list(identifiers)):
            rows = await db.execute(
                select(JobPosting)
                .options(*options)
                .where(JobPosting.source == source, JobPosting.external_id.in_(chunk))
                .order_by(JobPosting.date_first_seen)
            )
            for job in rows.scalars().unique():
                external[(source, job.external_id, job.company_id)] = job

    for provider, identifiers in external_by_provider.items():
        for chunk in _chunks(list(identifiers)):
            rows = await db.execute(
                select(JobPosting)
                .options(*options)
                .where(
                    JobPosting.collection_provider == provider,
                    JobPosting.external_id.in_(chunk),
                )
                .order_by(JobPosting.date_first_seen)
            )
            for job in rows.scalars().unique():
                provider_external[(provider, job.external_id, job.company_id)] = job

    for source, source_urls in urls_by_source.items():
        for chunk in _chunks(list(source_urls)):
            rows = await db.execute(
                select(JobPosting)
                .options(*options)
                .where(JobPosting.source == source, JobPosting.source_url.in_(chunk))
                .order_by(JobPosting.date_first_seen)
            )
            for job in rows.scalars().unique():
                urls[(source, job.source_url, job.company_id)] = job

    return {
        "external": external,
        "provider_external": provider_external,
        "urls": urls,
    }


async def get_or_create_company(name: str, db: AsyncSession) -> Company:
    normalized = normalize_company_name(name)
    result = await db.execute(select(Company).where(Company.name_normalized == normalized))
    company = result.scalar_one_or_none()
    if company:
        return company
    company = Company(name=name[:255], name_normalized=normalized[:255])
    db.add(company)
    await db.flush()
    log.info("company_created", name=name)
    return company


async def _find_existing(
    record: dict[str, Any],
    company_id: int,
    db: AsyncSession,
    prefetched: Optional[dict[str, dict[tuple[Any, ...], JobPosting]]] = None,
) -> Optional[JobPosting]:
    source = record["source"]
    provider = record.get("collection_provider") or source
    external_id = record.get("external_id")
    source_url = record.get("source_url")
    match: Optional[JobPosting] = None

    if prefetched is not None:
        candidates = []
        if external_id not in (None, ""):
            item = prefetched["provider_external"].get((provider, str(external_id), company_id))
            if item:
                candidates.append(item)
            item = prefetched["external"].get((source, str(external_id), company_id))
            if item:
                candidates.append(item)
        if source_url:
            item = prefetched["urls"].get((source, source_url, company_id))
            if item:
                candidates.append(item)
        if candidates:
            match = max(candidates, key=lambda job: job.date_first_seen or datetime.min)
    else:
        conditions = []
        if external_id not in (None, ""):
            conditions.append(and_(
                JobPosting.collection_provider == provider,
                JobPosting.external_id == str(external_id),
            ))
            conditions.append(and_(JobPosting.source == source, JobPosting.external_id == str(external_id)))
        if source_url:
            conditions.append(and_(JobPosting.source == source, JobPosting.source_url == source_url))
        if conditions:
            result = await db.execute(
                select(JobPosting)
                .options(
                    selectinload(JobPosting.snapshots),
                    selectinload(JobPosting.source_sightings),
                    selectinload(JobPosting.skills),
                )
                .where(JobPosting.company_id == company_id, or_(*conditions))
                .order_by(JobPosting.date_first_seen.desc())
                .limit(1)
            )
            match = result.scalar_one_or_none()

    if match:
        # Reappearance of a stable source ID after a long closed period is a
        # separate occurrence, not an update that erases history.
        if not match.is_active:
            gap = (utc_now() - match.date_last_seen).days
            if gap >= settings.repost_min_gap_days:
                return None
        return match

    # Content fallback is deliberately narrow and only used when a source gives
    # neither a stable ID nor a URL.
    if not external_id and not source_url:
        cutoff = utc_now() - timedelta(days=settings.parallel_listing_window_days)
        result = await db.execute(
            select(JobPosting).options(selectinload(JobPosting.snapshots), selectinload(JobPosting.source_sightings), selectinload(JobPosting.skills))
            .where(
                JobPosting.company_id == company_id,
                JobPosting.source == source,
                JobPosting.title_raw == record["title_raw"],
                JobPosting.location_raw == record.get("location_raw"),
                JobPosting.date_first_seen >= cutoff,
            ).order_by(JobPosting.date_first_seen.desc()).limit(1)
        )
        return result.scalar_one_or_none()
    return None


def _mutable_changed(job: JobPosting, record: dict[str, Any]) -> bool:
    return any((
        job.title_raw != record["title_raw"],
        (job.description_raw or "") != (record.get("description_raw") or ""),
        job.salary_min != record.get("salary_min"),
        job.salary_max != record.get("salary_max"),
        job.applicant_count != record.get("applicant_count"),
        job.location_raw != record.get("location_raw"),
        job.remote_type != record.get("remote_type"),
        job.employment_type != record.get("employment_type"),
        not job.is_active,
    ))


def _location_changed(job: JobPosting, record: dict[str, Any]) -> bool:
    return (
        job.location_raw != record.get("location_raw")
        or job.remote_type != record.get("remote_type")
        or job.employment_type != record.get("employment_type")
    )


async def _write_snapshot(job: JobPosting, db: AsyncSession, *, force: bool = False) -> bool:
    """Snapshot job's CURRENT field values -- must be called before
    _update_existing's field-mutation loop applies the incoming record, so a
    forced snapshot (force=True, meaning a meaningful field is about to
    change) captures the state immediately before that change, not after.

    Previously this snapshotted the incoming `record` after mutation had
    already been applied to `job`, so the very re-ingestion pass that wiped
    a field (e.g. description_raw, via the ingestion bug fixed alongside
    this one) produced a "historical" snapshot recording that same wiped
    value -- there was never a real "before" state on file to recover from.
    """
    latest = max(job.snapshots, key=lambda x: x.snapshot_at) if job.snapshots else None
    due = latest is None or utc_now() - latest.snapshot_at >= timedelta(hours=settings.snapshot_min_interval_hours)
    if not force and not due:
        return False
    db.add(JobSnapshot(
        job_posting_id=job.id,
        snapshot_at=utc_now(),
        source=job.source,
        applicant_count=job.applicant_count,
        description_raw=job.description_raw or None,
        description_hash=_desc_hash(job.description_raw or ""),
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        title_raw=job.title_raw,
        is_active=job.is_active,
    ))
    return True


async def _upsert_sightings(job: JobPosting, record: dict[str, Any], db: AsyncSession) -> None:
    existing = {sighting.sighting_key: sighting for sighting in job.source_sightings}
    # Migration 0006 assigns deterministic legacy keys before the Python URL
    # normalizer is available. Match the underlying identity as a fallback and
    # upgrade the key on the next observation instead of inserting a duplicate.
    existing_by_identity = {
        (
            sighting.source,
            normalize_source_url(sighting.source_url),
            str(sighting.external_id or ""),
        ): sighting
        for sighting in job.source_sightings
    }
    for option in record.get("source_options") or []:
        sighting_key = option["sighting_key"]
        source = option["source"]
        identity = (
            source,
            normalize_source_url(option.get("source_url")),
            str(option.get("external_id") or ""),
        )
        sighting = existing.get(sighting_key) or existing_by_identity.get(identity)
        if sighting is not None and sighting.sighting_key != sighting_key:
            existing.pop(sighting.sighting_key, None)
            sighting.sighting_key = sighting_key
            existing[sighting_key] = sighting
        if sighting is None:
            sighting = JobSourceSighting(
                job_posting_id=job.id,
                sighting_key=sighting_key,
                source=source,
                publisher_name=option.get("publisher_name"),
                collection_provider=option.get("collection_provider"),
                source_url=option.get("source_url"),
                external_id=option.get("external_id"),
                applicant_count=option.get("applicant_count"),
                is_direct=bool(option.get("is_direct", False)),
            )
            job.source_sightings.append(sighting)
            existing[sighting_key] = sighting
            existing_by_identity[identity] = sighting
            if source != job.source or option.get("source_url") != job.source_url:
                db.add(JobEvent(
                    job_posting_id=job.id,
                    event_type=EventType.source_added.value,
                    source=source,
                    payload={
                        "publisher_name": option.get("publisher_name"),
                        "collection_provider": option.get("collection_provider"),
                        "source_url": option.get("source_url"),
                        "is_direct": bool(option.get("is_direct", False)),
                    },
                ))
        else:
            sighting.last_seen = utc_now()
            sighting.publisher_name = option.get("publisher_name") or sighting.publisher_name
            sighting.collection_provider = option.get("collection_provider") or sighting.collection_provider
            sighting.source_url = option.get("source_url") or sighting.source_url
            sighting.external_id = option.get("external_id") or sighting.external_id
            sighting.is_direct = bool(option.get("is_direct", sighting.is_direct))
            if option.get("applicant_count") is not None:
                sighting.applicant_count = option.get("applicant_count")


async def _sync_skills(job: JobPosting, record: dict[str, Any], db: AsyncSession) -> None:
    existing = {skill.skill_normalized for skill in job.skills}
    for item in record.get("skills", []):
        normalized = item.get("skill_normalized") or str(item.get("skill", "")).lower()
        if normalized and normalized not in existing:
            job.skills.append(JobSkill(
                job_posting_id=job.id,
                skill=item.get("skill") or normalized,
                skill_normalized=normalized,
                skill_category=item.get("skill_category"),
            ))
            existing.add(normalized)


async def _update_existing(job: JobPosting, record: dict[str, Any], db: AsyncSession) -> JobPosting:
    now = utc_now()
    old = {
        "title": job.title_raw,
        "description_hash": _desc_hash(job.description_raw or ""),
        "salary": (job.salary_min, job.salary_max),
        "applicants": job.applicant_count,
        "active": job.is_active,
        "location": (job.location_raw, job.remote_type, job.employment_type),
    }
    changed = _mutable_changed(job, record)
    location_changed = _location_changed(job, record)

    # Must run before any of job's fields below are mutated -- see
    # _write_snapshot's docstring for why the ordering matters.
    await _write_snapshot(job, db, force=changed)

    if record["source"] == job.source:
        job.source_url = record.get("source_url") or job.source_url
        job.publisher_name = record.get("publisher_name") or job.publisher_name
    job.collection_provider = record.get("collection_provider") or job.collection_provider

    for field in (
        "title_raw", "title_normalized", "job_family", "specialization",
        "title_parse_confidence", "identity_fingerprint", "job_identity_key", "location_raw",
        "city", "state", "country", "metro_area", "latitude", "longitude",
        "remote_type", "seniority", "employment_type", "department", "industry",
        "salary_min", "salary_max", "salary_currency", "salary_listed",
        "education_required", "experience_years_min", "experience_years_max",
        "description_raw", "date_posted", "applicant_count",
    ):
        # description_raw and applicant_count used to be special-cased to
        # always overwrite, including with None. A re-collection pass whose
        # payload simply doesn't include a description (common -- some
        # providers only return full text on a per-job call, not the bulk
        # search call routine re-collection uses) would then silently wipe
        # a previously-stored description on every subsequent ingest. Every
        # field now follows the same rule: only overwrite when the incoming
        # value is actually present, never with absence.
        value = record.get(field)
        if value is not None:
            setattr(job, field, value)
    job.date_last_seen = now
    job.days_active = calculate_days_active(job.date_posted, job.date_first_seen, now)
    job.is_active = True

    if changed:
        _invalidate_scores(job)
    await _upsert_sightings(job, record, db)
    await _sync_skills(job, record, db)

    new_hash = _desc_hash(record.get("description_raw") or "")
    if old["title"] != job.title_raw:
        db.add(JobEvent(job_posting_id=job.id, event_type=EventType.title_changed.value, source=job.source, payload={"old": old["title"], "new": job.title_raw}))
    if old["description_hash"] != new_hash:
        db.add(JobEvent(job_posting_id=job.id, event_type=EventType.description_changed.value, source=job.source, payload={"old_hash": old["description_hash"], "new_hash": new_hash}))
    if old["salary"] != (job.salary_min, job.salary_max):
        db.add(JobEvent(job_posting_id=job.id, event_type=EventType.salary_changed.value, source=job.source, payload={"old": old["salary"], "new": [job.salary_min, job.salary_max]}))
    if old["applicants"] is not None and job.applicant_count is not None and job.applicant_count - old["applicants"] > 200:
        db.add(JobEvent(job_posting_id=job.id, event_type=EventType.applicant_spike.value, source=job.source, payload={"old": old["applicants"], "new": job.applicant_count}))
    if location_changed:
        db.add(JobEvent(
            job_posting_id=job.id,
            event_type=EventType.location_changed.value,
            source=job.source,
            payload={
                "old": {"location_raw": old["location"][0], "remote_type": old["location"][1], "employment_type": old["location"][2]},
                "new": {"location_raw": job.location_raw, "remote_type": job.remote_type, "employment_type": job.employment_type},
            },
        ))
    if not old["active"]:
        db.add(JobEvent(job_posting_id=job.id, event_type=EventType.reactivated.value, source=job.source))
    return job


async def _create_new(record: dict[str, Any], company: Company, db: AsyncSession) -> JobPosting:
    now = utc_now()
    job = JobPosting(
        company_id=company.id,
        job_identity_key=record["job_identity_key"],
        identity_fingerprint=record["identity_fingerprint"],
        listing_classification="original",
        external_id=str(record.get("external_id")) if record.get("external_id") not in (None, "") else None,
        source=record["source"],
        publisher_name=record.get("publisher_name"),
        collection_provider=record.get("collection_provider"),
        source_url=record.get("source_url"),
        title_raw=record["title_raw"], title_normalized=record["title_normalized"],
        job_family=record.get("job_family"), specialization=record.get("specialization"),
        title_parse_confidence=record.get("title_parse_confidence"),
        location_raw=record.get("location_raw"), city=record.get("city"), state=record.get("state"),
        country=record.get("country") or "US", metro_area=record.get("metro_area"),
        latitude=record.get("latitude"), longitude=record.get("longitude"), remote_type=record.get("remote_type"),
        seniority=record.get("seniority"), employment_type=record.get("employment_type"),
        department=record.get("department"), industry=record.get("industry"),
        salary_min=record.get("salary_min"), salary_max=record.get("salary_max"),
        salary_currency=record.get("salary_currency") or "USD", salary_listed=record.get("salary_listed", False),
        education_required=record.get("education_required"),
        experience_years_min=record.get("experience_years_min"),
        experience_years_max=record.get("experience_years_max"),
        description_raw=record.get("description_raw") or None, date_posted=record.get("date_posted"),
        date_first_seen=now, date_last_seen=now, is_active=True,
        days_active=calculate_days_active(record.get("date_posted"), now, now),
        applicant_count=record.get("applicant_count"), repost_count=0,
        source_sightings=[], snapshots=[], skills=[],
    )
    db.add(job)
    await db.flush()
    job.canonical_job_id = job.id

    for item in record.get("skills", []):
        normalized = item.get("skill_normalized") or str(item.get("skill", "")).lower()
        if normalized:
            job.skills.append(JobSkill(
                job_posting_id=job.id,
                skill=item.get("skill") or normalized,
                skill_normalized=normalized,
                skill_category=item.get("skill_category"),
            ))
    job.snapshots.append(JobSnapshot(
        job_posting_id=job.id,
        snapshot_at=now,
        source=record["source"],
        applicant_count=record.get("applicant_count"),
        description_raw=record.get("description_raw") or None,
        description_hash=_desc_hash(record.get("description_raw") or ""),
        salary_min=record.get("salary_min"),
        salary_max=record.get("salary_max"),
        title_raw=record["title_raw"],
        is_active=True,
    ))
    await _upsert_sightings(job, record, db)
    db.add(JobEvent(job_posting_id=job.id, event_type=EventType.created.value, source=job.source, payload={"identity_key": job.job_identity_key}))

    return job


async def _apply_provider_closure(job: JobPosting, record: dict[str, Any], db: AsyncSession) -> None:
    """Deactivate an existing row using the provider's own closed/inactive signal.

    Mirrors verify_listings.py's URL-based deactivation: mark inactive,
    invalidate scores, and record a JobEvent explaining why, without
    deleting history.
    """
    job.is_active = False
    _invalidate_scores(job)
    db.add(JobEvent(
        job_posting_id=job.id,
        event_type=EventType.expired.value,
        source=record.get("source") or job.source,
        payload={"method": "provider_reported_closed"},
        description="The collection provider's feed reported this listing as closed or inactive.",
    ))


async def upsert_job(
    raw: dict[str, Any],
    db: AsyncSession,
    *,
    prepared: bool = False,
    company: Optional[Company] = None,
    prefetched: Optional[dict[str, dict[tuple[Any, ...], JobPosting]]] = None,
) -> tuple[Optional[JobPosting], str]:
    record = raw if prepared else prepare_job_record(raw)
    company = company or await get_or_create_company(record["company_name"], db)
    existing = await _find_existing(record, company.id, db, prefetched)

    if record.get("provider_reports_closed"):
        # A conclusive negative signal from the provider itself: act on it if
        # we have a matching row to deactivate, otherwise there is nothing to
        # do (creating a new inactive row would be pointless).
        if existing and existing.is_active:
            await _apply_provider_closure(existing, record, db)
            return existing, "closed"
        return existing, "noop"

    if existing:
        job = await _update_existing(existing, record, db)
        return job, "updated"
    job = await _create_new(record, company, db)
    if prefetched is not None:
        if job.external_id:
            prefetched["external"][(job.source, job.external_id, job.company_id)] = job
            provider = job.collection_provider or job.source
            prefetched["provider_external"][(provider, job.external_id, job.company_id)] = job
        if job.source_url:
            prefetched["urls"][(job.source, job.source_url, job.company_id)] = job
    return job, "created"


async def ingest_jobs(jobs: list[dict[str, Any]], db: AsyncSession) -> dict[str, int]:
    created = updated = errors = closed = 0
    batch_size = settings.ingest_batch_size

    records: list[dict[str, Any]] = []
    for raw in jobs:
        try:
            records.append(prepare_job_record(raw))
        except Exception as exc:
            errors += 1
            log.error(
                "normalize_error",
                title=raw.get("title_raw", raw.get("title", "?")),
                source=raw.get("source"),
                error=str(exc),
            )

    if not records:
        return {"total": len(jobs), "created": 0, "updated": 0, "errors": errors, "closed": 0}

    company_cache = await _prepare_company_cache(records, db)
    prefetched = await _prefetch_existing_jobs(records, company_cache, db)

    for index, record in enumerate(records, start=1):
        try:
            company = company_cache[normalize_company_name(record["company_name"])]
            async with db.begin_nested():
                _, status = await upsert_job(
                    record,
                    db,
                    prepared=True,
                    company=company,
                    prefetched=prefetched,
                )
            created += int(status == "created")
            updated += int(status == "updated")
            closed += int(status == "closed")
        except Exception as exc:
            errors += 1
            log.error(
                "ingest_error",
                title=record.get("title_raw", "?"),
                source=record.get("source"),
                error=str(exc),
            )
            # A failed savepoint can expire eagerly loaded ORM state. Commit the
            # successful rows and rebuild caches for the remaining records so a
            # later item cannot trigger async lazy loading (MissingGreenlet).
            await db.commit()
            remaining = records[index:]
            if remaining:
                company_cache = await _prepare_company_cache(remaining, db)
                prefetched = await _prefetch_existing_jobs(remaining, company_cache, db)

        if index % batch_size == 0:
            await db.commit()
            log.info(
                "ingest_progress",
                processed=index,
                created=created,
                updated=updated,
                errors=errors,
                closed=closed,
            )

    await db.commit()
    return {"total": len(jobs), "created": created, "updated": updated, "errors": errors, "closed": closed}
