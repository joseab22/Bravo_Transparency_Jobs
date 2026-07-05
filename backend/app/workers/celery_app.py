"""Celery collection, enrichment, identity, and scoring tasks."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from celery import Celery
from celery.schedules import crontab
from redis import Redis
from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.time import utc_now
from app.db.session import AsyncSessionLocal
from app.models.models import JobPosting
from app.services.embedding_enrichment import enrich_embeddings
from app.services.location_enrichment import enrich_locations
from app.services.normalizer import calculate_days_active
from app.services.repost_detector import RepostDetectionService
from app.services.scoring import ScoringService
from app.workers.ingestion import ingest_jobs
from app.workers.scrapers import SCRAPER_REGISTRY

log = structlog.get_logger()
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

celery_app = Celery("joblens", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=25,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

SOURCE_SCHEDULES = {
    "indeed": crontab(minute=0, hour="*/6"),
    "linkedin": crontab(minute=10, hour="*/6"),
    "glassdoor": crontab(minute=20, hour="*/6"),
    "ziprecruiter": crontab(minute=30, hour="*/6"),
    "dice": crontab(minute=40, hour="*/6"),
    "monster": crontab(minute=50, hour="*/6"),
    "jobright": crontab(minute=5, hour="1,7,13,19"),
    "simplify": crontab(minute=0, hour=3),
}

beat_schedule = {
    f"scrape-{source}": {
        "task": "joblens.scrape_source",
        "schedule": SOURCE_SCHEDULES[source],
        "args": [source],
    }
    for source in settings.enabled_source_set
}
beat_schedule.update({
    "classify-listing-history": {"task": "joblens.run_repost_detection", "schedule": crontab(minute=30, hour=4)},
    "score-unscored-jobs": {"task": "joblens.score_all_jobs", "schedule": crontab(minute=15, hour="*")},
    "update-days-active": {"task": "joblens.update_days_active", "schedule": crontab(minute=0, hour=0)},
    "expire-stale-jobs": {"task": "joblens.expire_stale_jobs", "schedule": crontab(minute=15, hour=1)},
    "enrich-locations": {"task": "joblens.enrich_locations", "schedule": crontab(minute=35, hour="*")},
    "enrich-embeddings": {"task": "joblens.enrich_embeddings", "schedule": crontab(minute=45, hour="*")},
})
celery_app.conf.beat_schedule = beat_schedule

_worker_loop: asyncio.AbstractEventLoop | None = None


def run_async(coro):
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop.run_until_complete(coro)


def acquire_scrape_lock(source: str) -> tuple[str, str] | None:
    key, token = f"joblens:scrape-lock:{source}", str(uuid.uuid4())
    return (key, token) if redis_client.set(key, token, nx=True, ex=settings.scrape_lock_seconds) else None


def release_scrape_lock(key: str, token: str) -> None:
    redis_client.eval(
        "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0",
        1, key, token,
    )


@celery_app.task(name="joblens.scrape_source", bind=True, max_retries=3)
def task_scrape_source(self, source: str):
    source = source.lower()
    scrape_fn = SCRAPER_REGISTRY.get(source)
    if not scrape_fn:
        return {"status": "error", "error": f"Unknown source: {source}"}
    lock = acquire_scrape_lock(source)
    if not lock:
        log.warning("scrape_skipped_already_running", source=source)
        return {"source": source, "status": "skipped", "reason": "already running"}
    key, token = lock
    try:
        log.info("task_start", task="scrape_source", source=source)
        jobs = run_async(scrape_fn())
        result = run_async(_ingest(jobs))
        log.info("task_complete", source=source, **result)
        return {"source": source, "status": "completed", **result}
    except Exception as exc:
        log.exception("task_error", source=source, error=str(exc))
        raise self.retry(exc=exc, countdown=min(300 * (self.request.retries + 1), 1800))
    finally:
        release_scrape_lock(key, token)


@celery_app.task(name="joblens.run_repost_detection")
def task_run_repost_detection():
    return run_async(_repost_detection())


@celery_app.task(name="joblens.score_all_jobs")
def task_score_all_jobs(limit: int | None = None, force: bool = False):
    return run_async(_score_all(limit=limit, force=force))


@celery_app.task(name="joblens.analyze_hiring_activity")
def task_analyze_hiring_activity(limit: int | None = None):
    return run_async(_analyze_hiring_activity(limit))


@celery_app.task(name="joblens.update_days_active")
def task_update_days_active():
    return run_async(_update_days_active())


@celery_app.task(name="joblens.expire_stale_jobs")
def task_expire_stale_jobs():
    return run_async(_expire_stale())


@celery_app.task(name="joblens.enrich_locations")
def task_enrich_locations(limit: int | None = None):
    return run_async(_enrich_locations(limit))


@celery_app.task(name="joblens.enrich_embeddings")
def task_enrich_embeddings(limit: int | None = None):
    return run_async(_enrich_embeddings(limit))


async def _ingest(jobs: list[dict]) -> dict:
    async with AsyncSessionLocal() as db:
        return await ingest_jobs(jobs, db)


async def _repost_detection() -> dict:
    async with AsyncSessionLocal() as db:
        result = await RepostDetectionService().run_full_detection(db)
        await db.commit()
        return result


async def _score_all(limit: int | None = None, force: bool = False) -> dict:
    batch = limit or settings.scoring_batch_size
    async with AsyncSessionLocal() as db:
        query = select(JobPosting).options(
            selectinload(JobPosting.company), selectinload(JobPosting.snapshots),
            selectinload(JobPosting.embedding),
        ).where(JobPosting.is_active.is_(True))
        if not force:
            query = query.where(JobPosting.active_hiring_confidence.is_(None))
        jobs = list((await db.execute(query.order_by(JobPosting.id).limit(batch))).scalars().unique())
        scorer = ScoringService()
        scored = errors = 0
        for job in jobs:
            try:
                async with db.begin_nested():
                    await scorer.score_job(job, db)
                scored += 1
            except Exception as exc:
                errors += 1
                log.error("score_error", job_id=job.id, error=str(exc))
        companies_updated = await scorer.update_company_metrics(db)
        await db.commit()
        remaining = await db.scalar(select(func.count(JobPosting.id)).where(
            JobPosting.is_active.is_(True), JobPosting.active_hiring_confidence.is_(None)
        )) or 0
        return {"jobs_scored": scored, "errors": errors, "companies_updated": companies_updated, "remaining_unscored": remaining}


async def _analyze_hiring_activity(limit: int | None = None) -> dict:
    identity = await _repost_detection()
    scoring = await _score_all(limit=limit, force=False)
    return {"identity": identity, "scoring": scoring}


async def _update_days_active() -> dict:
    async with AsyncSessionLocal() as db:
        jobs = list((await db.execute(select(JobPosting).where(JobPosting.is_active.is_(True)))).scalars())
        now = utc_now()
        for job in jobs:
            job.days_active = calculate_days_active(job.date_posted, job.date_first_seen, now)
        await db.commit()
        return {"updated": len(jobs)}


async def _expire_stale() -> dict:
    if not settings.auto_expire_stale_jobs:
        return {"status": "disabled", "expired": 0}
    cutoff = utc_now() - timedelta(days=settings.stale_job_days)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(JobPosting).where(
                and_(JobPosting.is_active.is_(True), JobPosting.date_last_seen < cutoff)
            ).values(is_active=False, active_hiring_confidence=None)
        )
        await db.commit()
        return {"status": "completed", "expired": result.rowcount or 0}


async def _enrich_locations(limit: int | None) -> dict:
    async with AsyncSessionLocal() as db:
        return await enrich_locations(db, limit)


async def _enrich_embeddings(limit: int | None) -> dict:
    async with AsyncSessionLocal() as db:
        return await enrich_embeddings(db, limit)
