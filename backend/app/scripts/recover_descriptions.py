"""Recover job descriptions wiped by the ingestion.py re-collection bug
(fixed alongside this script -- see that file's history).

A re-collection pass whose payload didn't include a description used to
overwrite job_postings.description_raw with NULL unconditionally. This
looks for the most recent job_snapshots row still holding real text for
each affected job and, on --apply, restores it.

Read-only by default. Nothing is written to the database unless --apply
is passed explicitly.

Examples:
    python -m app.scripts.recover_descriptions
    python -m app.scripts.recover_descriptions --apply
    python -m app.scripts.recover_descriptions --apply --limit 500
"""
from __future__ import annotations

import argparse
import asyncio

import structlog
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.models import JobPosting, JobSnapshot
from app.services.repost_detector import SCORE_FIELDS

log = structlog.get_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write recovered descriptions to the database.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to process.")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, int]:
    affected = 0
    recovered = 0
    unrecoverable = 0

    async with AsyncSessionLocal() as db:
        missing_query = select(JobPosting.id).where(
            (JobPosting.description_raw.is_(None)) | (JobPosting.description_raw == "")
        )
        if args.limit:
            missing_query = missing_query.limit(args.limit)
        missing_ids = list((await db.execute(missing_query)).scalars())
        affected = len(missing_ids)

        for job_id in missing_ids:
            best_snapshot = (await db.execute(
                select(JobSnapshot.description_raw)
                .where(
                    JobSnapshot.job_posting_id == job_id,
                    JobSnapshot.description_raw.is_not(None),
                    JobSnapshot.description_raw != "",
                )
                .order_by(JobSnapshot.snapshot_at.desc())
                .limit(1)
            )).scalar_one_or_none()

            if not best_snapshot:
                unrecoverable += 1
                continue

            recovered += 1
            if args.apply:
                job = await db.get(JobPosting, job_id)
                if job is None:
                    continue
                job.description_raw = best_snapshot
                # A restored description is a real, meaningful field change --
                # any score computed while it was missing was computed against
                # incomplete data, so it must be recomputed, not left stale.
                for field in SCORE_FIELDS:
                    setattr(job, field, None)

        if args.apply and recovered:
            await db.commit()

    return {
        "jobs_missing_description": affected,
        "recoverable_from_snapshot_history": recovered,
        "not_recoverable": unrecoverable,
        "applied": recovered if args.apply else 0,
    }


def main() -> None:
    args = parse_args()
    summary = asyncio.run(run(args))
    log.info("recover_descriptions_summary", mode="apply" if args.apply else "dry_run", **summary)
    print(summary)
    if not args.apply and summary["recoverable_from_snapshot_history"]:
        print(
            "\nDry run only -- nothing was written. Re-run with --apply to restore "
            f"{summary['recoverable_from_snapshot_history']} description(s)."
        )


if __name__ == "__main__":
    main()
