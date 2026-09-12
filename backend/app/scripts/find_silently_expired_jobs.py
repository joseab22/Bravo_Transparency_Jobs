"""Find jobs deactivated by the blind stale-job-expiry task rather than by
conclusive evidence the listing itself closed.

Exactly three code paths ever set job_postings.is_active = False:

  - verify_listings.py's direct URL check (writes a JobEvent with
    event_type="expired", payload.method="direct_url_verification")
  - ingestion.py's provider-reported-closure path (writes a JobEvent with
    event_type="expired", payload.method="provider_reported_closed")
  - celery_app.py's _expire_stale() bulk task, which deactivates any job
    not re-seen by ANY source within stale_job_days and writes NO JobEvent
    at all

An inactive job with no "expired" JobEvent on record was therefore
deactivated by the bulk staleness task -- it has no conclusive evidence of
closure, only "nothing re-confirmed it recently", which is exactly the
ambiguous signal this project's own rules say should leave a listing
active for review, not auto-deactivate it. This matters most right now
because an entire collection source (JSearch) can stop confirming its own
previously-found postings for reasons that have nothing to do with
whether the job itself is still open (e.g. exhausted API quota) -- this
task can't tell the difference.

Read-only by default. --apply reactivates the affected jobs (clears
is_active back to True, leaves scores at whatever _expire_stale() already
nulled them to so the normal scoring pipeline recomputes them fresh, and
records a JobEvent explaining the reactivation -- unlike the deactivation
that caused this, so the trail exists next time).

Examples:
    python -m app.scripts.find_silently_expired_jobs
    python -m app.scripts.find_silently_expired_jobs --apply
    python -m app.scripts.find_silently_expired_jobs --apply --limit 500
"""
from __future__ import annotations

import argparse
import asyncio

import structlog
from sqlalchemy import select

from app.core.time import utc_now
from app.models.models import EventType, JobEvent, JobPosting
from app.db.session import AsyncSessionLocal

log = structlog.get_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Reactivate the affected jobs.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to reactivate.")
    parser.add_argument("--sample", type=int, default=10, help="How many example jobs to print (dry run only).")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        inactive_ids = list((await db.execute(
            select(JobPosting.id).where(JobPosting.is_active.is_(False))
        )).scalars())

        explained_ids = set((await db.execute(
            select(JobEvent.job_posting_id.distinct()).where(
                JobEvent.job_posting_id.in_(inactive_ids),
                JobEvent.event_type == EventType.expired.value,
            )
        )).scalars())

        silently_expired_ids = [job_id for job_id in inactive_ids if job_id not in explained_ids]

        if not args.apply:
            sample_rows = list((await db.execute(
                select(JobPosting.id, JobPosting.title_raw, JobPosting.date_last_seen)
                .where(JobPosting.id.in_(silently_expired_ids[: args.sample]))
            )).all())
            for job_id, title, last_seen in sample_rows:
                print(f"  {job_id:>8}  last_seen={last_seen}  {title!r}")

        reactivated = 0
        if args.apply:
            target_ids = silently_expired_ids[: args.limit] if args.limit else silently_expired_ids
            for job_id in target_ids:
                job = await db.get(JobPosting, job_id)
                if job is None or job.is_active:
                    continue
                job.is_active = True
                db.add(JobEvent(
                    job_posting_id=job.id,
                    event_type=EventType.reactivated.value,
                    description=(
                        "Reactivated: this job had no conclusive evidence of closure on record "
                        "(no 'expired' JobEvent), so it was deactivated only because no source had "
                        "re-confirmed it recently -- not because the listing was verified closed."
                    ),
                    payload={"method": "silently_expired_recovery", "reactivated_at": utc_now().isoformat()},
                ))
                reactivated += 1
            if reactivated:
                await db.commit()

    return {
        "total_inactive": len(inactive_ids),
        "deactivated_with_explanation": len(explained_ids),
        "silently_expired_no_explanation": len(silently_expired_ids),
        "reactivated": reactivated,
    }


def main() -> None:
    args = parse_args()
    summary = asyncio.run(run(args))
    log.info("find_silently_expired_jobs_summary", mode="apply" if args.apply else "dry_run", **summary)
    print(summary)
    if not args.apply and summary["silently_expired_no_explanation"]:
        print(
            "\nDry run only -- nothing was written. Re-run with --apply to reactivate "
            f"{summary['silently_expired_no_explanation']} job(s)."
        )


if __name__ == "__main__":
    main()
