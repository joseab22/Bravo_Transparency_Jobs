"""
Celery app — all 8 scraper tasks + analytics tasks.
"""
import asyncio
import uuid
from celery import Celery
from celery.schedules import crontab
from redis import Redis
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

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
SCRAPE_LOCK_SECONDS = 30 * 60

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
    worker_max_tasks_per_child=50,
    result_expires=3600,
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



def acquire_scrape_lock(source: str) -> tuple[str, str] | None:
    """Acquire one Redis lock per source so duplicate scrapes cannot overlap."""
    lock_key = f"joblens:scrape-lock:{source}"
    lock_token = str(uuid.uuid4())
    acquired = redis_client.set(
        lock_key,
        lock_token,
        nx=True,
        ex=SCRAPE_LOCK_SECONDS,
    )
    if not acquired:
        return None
    return lock_key, lock_token


def release_scrape_lock(lock_key: str, lock_token: str) -> None:
    """Release the lock only when the current task still owns it."""
    release_script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    end
    return 0
    """
    redis_client.eval(release_script, 1, lock_key, lock_token)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="joblens.scrape_source", bind=True, max_retries=3)
def task_scrape_source(self, source: str):
    """Run one source scraper while preventing duplicate overlapping runs."""
    scrape_fn = SCRAPER_REGISTRY.get(source)
    if not scrape_fn:
        log.error("unknown_source", source=source)
        return {"error": f"Unknown source: {source}"}

    lock = acquire_scrape_lock(source)
    if lock is None:
        log.warning("scrape_skipped_already_running", source=source)
        return {
            "source": source,
            "status": "skipped",
            "reason": "A scraper task for this source is already running",
        }

    lock_key, lock_token = lock
    log.info("task_start", task="scrape_source", source=source)

    try:
        jobs = run_async(scrape_fn())
        result = run_async(_ingest(jobs))
        log.info("task_complete", source=source, **result)
        return {"source": source, "status": "completed", **result}
    except Exception as exc:
        log.error("task_error", source=source, error=str(exc))
        countdown = min(300 * (self.request.retries + 1), 1800)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        release_scrape_lock(lock_key, lock_token)


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
        result = await db.execute(
            select(JobPosting)
            .where(and_(JobPosting.is_active == True, JobPosting.health_score == None))
            .limit(500)
        )
        jobs = result.scalars().all()
        scorer = ScoringService()
        scored = 0
        for job in jobs:
            try:
                await scorer.score_job(job, db)
                scored += 1
            except Exception as e:
                log.error("score_error", job_id=job.id, error=str(e))
        await db.commit()
        return {"jobs_scored": scored}


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
