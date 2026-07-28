"""Recompute normalized role identity fields for existing JobLens postings.

This uses the same Python normalizer as ingestion and repost detection, avoiding
an independent SQL rule list that can drift from application behavior.

Run a preview:
    docker compose exec -w /app backend \
      python -m app.scripts.backfill_job_identity --dry-run

Apply the backfill:
    docker compose exec -w /app backend \
      python -m app.scripts.backfill_job_identity
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.models import JobPosting
from app.services.normalizer import (
    build_identity_fingerprint,
    build_job_identity_key,
    decompose_title,
)
from app.services.repost_detector import SCORE_FIELDS


def _resolved_seniority(current: str | None, parsed: str | None) -> str | None:
    """Prefer explicit title seniority while preserving useful provider data."""
    if parsed and parsed != "Mid":
        return parsed
    return current or parsed


def _new_identity_values(job: JobPosting) -> dict[str, Any]:
    parts = decompose_title(job.title_raw)
    family = parts["job_family"] or parts["title_normalized"]
    seniority = _resolved_seniority(job.seniority, parts["seniority"])
    company_name: Any = job.company.name if job.company else job.company_id

    return {
        "title_normalized": parts["title_normalized"][:500],
        "job_family": family[:500] if family else None,
        "specialization": (
            parts["specialization"][:300]
            if parts["specialization"]
            else None
        ),
        "seniority": seniority,
        "title_parse_confidence": parts["confidence"],
        "identity_fingerprint": build_identity_fingerprint(
            company_name,
            family,
            parts["specialization"],
            seniority,
            job.employment_type,
            job.remote_type,
        ),
        "job_identity_key": build_job_identity_key(
            company_name,
            family,
            job.metro_area,
            specialization=parts["specialization"],
            seniority=seniority,
            employment_type=job.employment_type,
            remote_type=job.remote_type,
        ),
    }


async def backfill(*, batch_size: int, dry_run: bool) -> None:
    total = 0
    changed_jobs = 0
    invalidated_jobs = 0
    changed_fields: Counter[str] = Counter()
    last_id = 0

    async with AsyncSessionLocal() as db:
        while True:
            result = await db.execute(
                select(JobPosting)
                .options(selectinload(JobPosting.company))
                .where(JobPosting.id > last_id)
                .order_by(JobPosting.id)
                .limit(batch_size)
            )
            jobs = list(result.scalars().unique())
            if not jobs:
                break

            for job in jobs:
                total += 1
                last_id = job.id
                new_values = _new_identity_values(job)
                differences = {
                    field: value
                    for field, value in new_values.items()
                    if getattr(job, field) != value
                }
                if not differences:
                    continue

                changed_jobs += 1
                changed_fields.update(differences.keys())

                if dry_run:
                    continue

                for field, value in differences.items():
                    setattr(job, field, value)

                # Identity changes can alter parallel/repost classification and
                # every score derived from that classification.
                for field in SCORE_FIELDS:
                    setattr(job, field, None)
                invalidated_jobs += 1

            if not dry_run:
                await db.commit()

            print(
                f"processed={total} changed={changed_jobs} "
                f"last_id={last_id} dry_run={dry_run}"
            )

    print("\nBackfill complete")
    print(f"jobs_processed={total}")
    print(f"jobs_changed={changed_jobs}")
    print(f"jobs_scores_invalidated={invalidated_jobs}")
    print("field_changes=" + repr(dict(changed_fields)))
    if dry_run:
        print("No database changes were written.")
    else:
        print("Run repost detection and forced rescoring next.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill normalized JobLens role identity fields."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Rows committed per batch (default: 1000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing them.",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    asyncio.run(backfill(batch_size=args.batch_size, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
