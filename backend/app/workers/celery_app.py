"""
Celery app — all 8 scraper tasks + analytics tasks.
"""
import asyncio
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select, and_, update
from datetime import datetime, timedelta

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.models import JobPosting
from app.services.scoring import ScoringService
from app.services.repost_detector import RepostDetectionService
from app.workers.scrapers import SCRAPER_REGISTRY
from app.workers.ingestion import ingest_jobs

import structlog
log = structlog.get_logger()

celery_app = Celery("joblens", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=50,
)

celery_app.conf.beat_schedule = {
    # --- Scrapers: staggered to avoid rate limit collisions ---
    "scrape-indeed-every-6h":        {"task": "joblens.scrape_source", "schedule": crontab(minute=0,  hour="*/6"),  "args": ["indeed"]},
    "scrape-linkedin-every-6h":      {"task": "joblens.scrape_source", "schedule": crontab(minute=10, hour="*/6"),  "args": ["linkedin"]},
    "scrape-glassdoor-every-6h":     {"task": "joblens.scrape_source", "schedule": crontab(minute=20, hour="*/6"),  "args": ["glassdoor"]},
    "scrape-ziprecruiter-every-6h":  {"task": "joblens.scrape_source", "schedule": crontab(minute=30, hour="*/6"),  "args": ["ziprecruiter"]},
    "scrape-dice-every-6h":          {"task": "joblens.scrape_source", "schedule": crontab(minute=40, hour="*/6"),  "args": ["dice"]},
    "scrape-monster-every-6h":       {"task": "joblens.scrape_source", "schedule": crontab(minute=50, hour="*/6"),  "args": ["monster"]},
    "scrape-jobright-every-6h":      {"task": "joblens.scrape_source", "schedule": crontab(minute=5,  hour="1,7,13,19"), "args": ["jobright"]},
    "scrape-simplify-daily":         {"task": "joblens.scrape_source", "schedule": crontab(minute=0,  hour=3),      "args": ["simplify"]},  # once/day (GitHub feed)
    # --- Analytics ---
    "repost-detection-daily":   {"task": "joblens.run_repost_detection", "schedule": crontab(minute=30, hour=2)},
    "score-jobs-every-3h":      {"task": "joblens.score_all_jobs",       "schedule": crontab(minute=0,  hour="*/3")},
    "update-days-active-daily": {"task": "joblens.update_days_active",   "schedule": crontab(minute=0,  hour=0)},
    "expire-stale-jobs-daily":  {"task": "joblens.expire_stale_jobs",    "schedule": crontab(minute=15, hour=1)},
}


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="joblens.scrape_source", bind=True, max_retries=3)
def task_scrape_source(self, source: str):
    """Universal scraper task — dispatches to the correct adapter by source name."""
    scrape_fn = SCRAPER_REGISTRY.get(source)
    if not scrape_fn:
        log.error("unknown_source", source=source)
        return {"error": f"Unknown source: {source}"}
    log.info("task_start", task="scrape_source", source=source)
    try:
        jobs = run_async(scrape_fn())
        result = run_async(_ingest(jobs))
        log.info("task_complete", source=source, **result)
        return result
    except Exception as exc:
        log.error("task_error", source=source, error=str(exc))
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(name="joblens.run_repost_detection", bind=True)
def task_run_repost_detection(self):
    log.info("task_start", task="repost_detection")
    result = run_async(_repost_detection())
    log.info("task_complete", task="repost_detection", **result)
    return result


@celery_app.task(name="joblens.score_all_jobs", bind=True)
def task_score_all_jobs(self):
    log.info("task_start", task="score_all_jobs")
    result = run_async(_score_all())
    log.info("task_complete", **result)
    return result


@celery_app.task(name="joblens.update_days_active", bind=True)
def task_update_days_active(self):
    run_async(_update_days_active())


@celery_app.task(name="joblens.expire_stale_jobs", bind=True)
def task_expire_stale_jobs(self, stale_after_days: int = 14):
    run_async(_expire_stale(stale_after_days))


# ---------------------------------------------------------------------------
# Async implementations
# ---------------------------------------------------------------------------

async def _ingest(jobs: list[dict]) -> dict:
    async with AsyncSessionLocal() as db:
        return await ingest_jobs(jobs, db)


async def _repost_detection() -> dict:
    async with AsyncSessionLocal() as db:
        service = RepostDetectionService()
        result = await service.run_full_detection(db)
        await db.commit()
        return result


async def _score_all() -> dict:
    async with AsyncSessionLocal() as db:
        scorer = ScoringService()
        scored = 0
        errors = 0
        last_id = 0

        # Re-score every active job in bounded batches because age, applicant
        # trends, parallel listings, and repost classification change over time.
        while True:
            result = await db.execute(
                select(JobPosting)
                .where(
                    and_(
                        JobPosting.is_active == True,
                        JobPosting.id > last_id,
                    )
                )
                .order_by(JobPosting.id)
                .limit(500)
            )
            jobs = list(result.scalars().all())
            if not jobs:
                break

            for job in jobs:
                try:
                    await scorer.score_job(job, db)
                    scored += 1
                except Exception as exc:
                    errors += 1
                    log.error("score_error", job_id=job.id, error=str(exc))

            last_id = jobs[-1].id
            await db.flush()

        await db.commit()
        return {"jobs_scored": scored, "errors": errors}


async def _update_days_active():
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(JobPosting).where(JobPosting.is_active == True)
            .values(days_active=JobPosting.days_active + 1)
        )
        await db.commit()


async def _expire_stale(stale_after_days: int):
    cutoff = datetime.utcnow() - timedelta(days=stale_after_days)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(JobPosting)
            .where(and_(JobPosting.is_active == True, JobPosting.date_last_seen < cutoff))
            .values(is_active=False)
        )
        await db.commit()
