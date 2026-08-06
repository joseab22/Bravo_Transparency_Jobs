"""Check active JobLens listing URLs and deactivate conclusively closed jobs.

Examples:
    python -m app.scripts.verify_listings --dry-run --limit 100
    python -m app.scripts.verify_listings --recheck-days 1
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.time import utc_now
from app.db.session import AsyncSessionLocal
from app.models.models import JobEvent, JobPosting
from app.services.listing_verification import ListingAvailabilityVerifier
from app.services.repost_detector import SCORE_FIELDS

log = structlog.get_logger()
CHECK_EVENT = "availability_checked"
EXPIRED_EVENT = "expired"
REACTIVATED_EVENT = "reactivated"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check every active JobLens URL. Jobs are deactivated only when all known "
            "URLs conclusively show that the listing is closed."
        )
    )
    parser.add_argument("--dry-run", action="store_true", help="Create a report without changing the database.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to process.")
    parser.add_argument("--start-after-id", type=int, default=0, help="Start after this job ID.")
    parser.add_argument(
        "--job-id",
        type=int,
        action="append",
        default=None,
        help="Check one specific job ID. Repeat this option to check multiple IDs.",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Also check rows currently marked inactive.",
    )
    parser.add_argument(
        "--reactivate-active",
        action="store_true",
        help=(
            "Reactivate an inactive row when one of its exact known URLs is confirmed active. "
            "Use this only after reviewing the listing identity manually."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=100, help="Database commit batch size.")
    parser.add_argument("--concurrency", type=int, default=6, help="Maximum simultaneous requests across domains.")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds.")
    parser.add_argument("--attempts", type=int, default=2, help="Attempts for temporary failures.")
    parser.add_argument("--per-domain-delay", type=float, default=1.0, help="Minimum seconds between requests to one domain.")
    parser.add_argument("--max-body-kb", type=int, default=256, help="Maximum response body read per URL.")
    parser.add_argument(
        "--recheck-days",
        type=int,
        default=1,
        help=(
            "Skip jobs successfully checked within this many days. Use 0 to check all active jobs again. "
            "The default allows a stopped run to resume without repeating today's completed checks."
        ),
    )
    parser.add_argument(
        "--report-dir",
        default="/app/availability_reports",
        help="Directory for JSONL details and summary files.",
    )
    return parser.parse_args()


def _job_urls(job: JobPosting) -> list[str]:
    values = [job.source_url]
    values.extend(item.source_url for item in (job.source_sightings or []))
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = (value or "").strip()
        if clean and clean not in seen:
            output.append(clean)
            seen.add(clean)
    return output


def _report_record(job: JobPosting, result, *, changed: bool, was_active: bool) -> dict[str, Any]:
    return {
        "checked_at": utc_now().isoformat(),
        "job_id": job.id,
        "title": job.title_raw,
        "company": job.company.name if job.company else None,
        "source": job.source,
        "collection_provider": job.collection_provider,
        "was_active": was_active,
        "database_changed": changed,
        **result.as_dict(),
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.reactivate_active:
        args.include_inactive = True

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    mode = "dry_run" if args.dry_run else "apply"
    detail_path = report_dir / f"listing_verification_{stamp}_{mode}.jsonl"
    summary_path = report_dir / f"listing_verification_{stamp}_{mode}_summary.json"

    counts: Counter[str] = Counter()
    processed = 0
    deactivated = 0
    reactivated = 0
    current_id = max(args.start_after_id, 0)
    selected_job_ids = sorted(set(args.job_id or []))
    cutoff = utc_now() - timedelta(days=max(args.recheck_days, 0))

    last_check = (
        select(
            JobEvent.job_posting_id.label("job_posting_id"),
            func.max(JobEvent.timestamp).label("last_check_at"),
        )
        .where(JobEvent.event_type == CHECK_EVENT)
        .group_by(JobEvent.job_posting_id)
        .subquery()
    )

    verifier = ListingAvailabilityVerifier(
        concurrency=args.concurrency,
        request_timeout=args.timeout,
        attempts=args.attempts,
        per_domain_delay=args.per_domain_delay,
        max_body_bytes=args.max_body_kb * 1024,
    )

    try:
        with detail_path.open("a", encoding="utf-8") as detail_file:
            while args.limit is None or processed < args.limit:
                remaining = len(selected_job_ids) if selected_job_ids else args.batch_size
                if args.limit is not None:
                    remaining = min(remaining, args.limit - processed)
                if remaining <= 0:
                    break

                async with AsyncSessionLocal() as db:
                    query = (
                        select(JobPosting)
                        .options(
                            selectinload(JobPosting.company),
                            selectinload(JobPosting.source_sightings),
                        )
                        .outerjoin(last_check, last_check.c.job_posting_id == JobPosting.id)
                    )
                    if selected_job_ids:
                        query = query.where(JobPosting.id.in_(selected_job_ids))
                    else:
                        query = query.where(JobPosting.id > current_id)
                    if not args.include_inactive:
                        query = query.where(JobPosting.is_active.is_(True))
                    if args.recheck_days > 0:
                        query = query.where(
                            or_(
                                last_check.c.last_check_at.is_(None),
                                last_check.c.last_check_at < cutoff,
                            )
                        )
                    jobs = list(
                        (
                            await db.execute(
                                query.order_by(JobPosting.id).limit(remaining)
                            )
                        )
                        .scalars()
                        .unique()
                    )
                    if not jobs:
                        break

                    results = await asyncio.gather(
                        *(verifier.verify_job(job.id, _job_urls(job)) for job in jobs)
                    )
                    by_id = {item.job_id: item for item in results}

                    for job in jobs:
                        current_id = max(current_id, job.id)
                        result = by_id[job.id]
                        counts[result.outcome] += 1
                        changed = False

                        was_active = bool(job.is_active)
                        payload = result.as_dict()
                        payload["checked_at"] = utc_now().isoformat()
                        if not args.dry_run:
                            db.add(
                                JobEvent(
                                    job_posting_id=job.id,
                                    event_type=CHECK_EVENT,
                                    source=job.source,
                                    payload=payload,
                                    description=result.reason[:500],
                                )
                            )
                            if result.outcome == "inactive" and job.is_active:
                                job.is_active = False
                                for field in SCORE_FIELDS:
                                    setattr(job, field, None)
                                changed = True
                                deactivated += 1
                                db.add(
                                    JobEvent(
                                        job_posting_id=job.id,
                                        event_type=EXPIRED_EVENT,
                                        source=job.source,
                                        payload={
                                            "method": "direct_url_verification",
                                            "verification": payload,
                                        },
                                        description="All known listing URLs were conclusively closed.",
                                    )
                                )
                            elif (
                                result.outcome == "active"
                                and not job.is_active
                                and args.reactivate_active
                            ):
                                job.is_active = True
                                job.date_last_seen = utc_now()
                                for field in SCORE_FIELDS:
                                    setattr(job, field, None)
                                changed = True
                                reactivated += 1
                                db.add(
                                    JobEvent(
                                        job_posting_id=job.id,
                                        event_type=REACTIVATED_EVENT,
                                        source=job.source,
                                        payload={
                                            "method": "direct_url_verification",
                                            "verification": payload,
                                        },
                                        description="A manually selected inactive listing URL was confirmed active.",
                                    )
                                )

                        record = _report_record(job, result, changed=changed, was_active=was_active)
                        detail_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                        detail_file.flush()
                        processed += 1

                    if not args.dry_run:
                        await db.commit()

                if selected_job_ids:
                    break

                log.info(
                    "listing_verification_progress",
                    processed=processed,
                    active=counts["active"],
                    inactive=counts["inactive"],
                    unknown=counts["unknown"],
                    deactivated=deactivated,
                    reactivated=reactivated,
                    last_job_id=current_id,
                )
    finally:
        await verifier.close()

    summary = {
        "mode": mode,
        "processed": processed,
        "confirmed_active": counts["active"],
        "confirmed_inactive": counts["inactive"],
        "unknown_or_blocked": counts["unknown"],
        "deactivated": deactivated,
        "reactivated": reactivated,
        "last_job_id": current_id,
        "detail_report": str(detail_path),
        "summary_report": str(summary_path),
        "finished_at": utc_now().isoformat(),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    summary = asyncio.run(run(args))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
