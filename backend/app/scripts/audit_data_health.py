"""Data-first health audit -- checks the live database for anomalies before
assuming any explanation from reading code.

This exists because of a real miss: a prior investigation into missing job
descriptions jumped to a plausible-looking code defect (an ingestion.py
overwrite-with-None bug) without first checking whether the missing data
actually correlated with anything. It didn't -- the real cause (Simplify's
feed never provides description text at all) was visible immediately from
a single GROUP BY source query, which wasn't run until several fixes later.
This script generalizes that specific check, plus a few other structural
checks worth confirming after the recent incidents, so the same mistake
doesn't need to repeat itself for some other field.

Entirely read-only.

Examples:
    python -m app.scripts.audit_data_health
    python -m app.scripts.audit_data_health --min-source-count 100
"""
from __future__ import annotations

import argparse
import asyncio

import structlog
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.models import EventType, JobEvent, JobPosting

log = structlog.get_logger()

# Every meaningful nullable field a scraper is expected to populate at least
# some of the time. Deliberately excludes fields that are legitimately
# almost-always-null by design (e.g. canonical_job_id) or score fields
# (checked separately below, since NULL there means "pending rescore", not
# "missing data").
CHECKED_FIELDS = [
    "description_raw",
    "salary_min",
    "salary_max",
    "applicant_count",
    "location_raw",
    "employment_type",
    "seniority",
    "department",
    "industry",
    "education_required",
    "experience_years_min",
]

SCORE_FIELDS = (
    "ghost_job_probability", "ghost_confidence", "health_score",
    "competition_score", "interview_opportunity_score", "salary_fairness_score",
    "activity_score", "active_hiring_confidence",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--min-source-count", type=int, default=30,
        help="Ignore sources with fewer than this many rows -- avoids flagging noise from tiny long-tail sources.",
    )
    parser.add_argument(
        "--flag-ratio", type=float, default=2.0,
        help="Flag a source if its missing-rate is at least this many times the field's overall missing-rate.",
    )
    return parser.parse_args()


async def check_field_completeness_by_source(db, field_name: str, min_source_count: int, flag_ratio: float) -> list[dict]:
    column = getattr(JobPosting, field_name)
    is_string_field = column.type.python_type is str
    is_missing = (column.is_(None) | (column == "")) if is_string_field else column.is_(None)

    overall = (await db.execute(
        select(
            func.count(JobPosting.id),
            func.count(JobPosting.id).filter(is_missing),
        )
    )).one()
    overall_total, overall_missing = overall
    if overall_total == 0:
        return []
    overall_rate = overall_missing / overall_total

    rows = (await db.execute(
        select(
            JobPosting.source,
            func.count(JobPosting.id),
            func.count(JobPosting.id).filter(is_missing),
        ).group_by(JobPosting.source)
    )).all()

    flagged = []
    for source, total, missing in rows:
        if total < min_source_count:
            continue
        rate = missing / total
        # Only flag sources doing meaningfully WORSE than the overall rate --
        # a source with 0% missing when the overall rate is already 0% isn't
        # a finding, and a low-volume field-wide gap isn't this source's fault.
        if rate > 0 and overall_rate < 0.999 and rate >= max(overall_rate * flag_ratio, 0.5):
            flagged.append({
                "field": field_name, "source": source, "total": total,
                "missing": missing, "rate": rate, "overall_rate": overall_rate,
            })
    return flagged


async def check_expiry_audit_trail(db) -> dict:
    inactive_ids = list((await db.execute(
        select(JobPosting.id).where(JobPosting.is_active.is_(False))
    )).scalars())
    if not inactive_ids:
        return {"total_inactive": 0, "unexplained": 0}
    explained_ids = set((await db.execute(
        select(JobEvent.job_posting_id.distinct()).where(
            JobEvent.job_posting_id.in_(inactive_ids),
            JobEvent.event_type == EventType.expired.value,
        )
    )).scalars())
    return {
        "total_inactive": len(inactive_ids),
        "unexplained": len(inactive_ids) - len(explained_ids),
    }


async def check_score_pending(db) -> dict:
    active_total = await db.scalar(select(func.count(JobPosting.id)).where(JobPosting.is_active.is_(True)))
    pending = await db.scalar(
        select(func.count(JobPosting.id)).where(
            JobPosting.is_active.is_(True),
            JobPosting.active_hiring_confidence.is_(None),
        )
    )
    return {"active_total": active_total or 0, "pending_rescore": pending or 0}


async def run(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as db:
        print("=== Field completeness anomalies by source ===")
        any_flagged = False
        for field_name in CHECKED_FIELDS:
            flagged = await check_field_completeness_by_source(db, field_name, args.min_source_count, args.flag_ratio)
            for item in flagged:
                any_flagged = True
                print(
                    f"  {item['field']:<22} source={item['source']:<20} "
                    f"missing {item['missing']}/{item['total']} ({item['rate']:.0%}) "
                    f"vs overall {item['overall_rate']:.0%}"
                )
        if not any_flagged:
            print("  none found")

        print("\n=== Deactivation audit-trail completeness ===")
        expiry = await check_expiry_audit_trail(db)
        print(f"  total_inactive={expiry['total_inactive']}  unexplained={expiry['unexplained']}")
        if expiry["unexplained"]:
            print(
                "  ^ these are inactive with no 'expired' JobEvent -- either new silent expiries "
                "(check AUTO_EXPIRE_STALE_JOBS) or a different, not-yet-found deactivation path."
            )

        print("\n=== Score pending (active jobs with no active_hiring_confidence) ===")
        pending = await check_score_pending(db)
        print(f"  {pending['pending_rescore']} of {pending['active_total']} active jobs pending rescore")


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
