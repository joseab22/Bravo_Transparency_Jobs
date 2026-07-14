from __future__ import annotations

import math
from typing import Optional, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import Company, JobPosting, JobSkill, JobSourceSighting
from app.schemas.jobs import JobPostingDetail, JobPostingListItem, MarketStats, PaginatedJobsResponse
from app.services.scoring import ScoringService
from app.services.source_attribution import canonical_group_id, load_canonical_sources

router = APIRouter(prefix="/jobs", tags=["jobs"])
SORT_COLS = {
    "active_hiring_confidence", "health_score", "ghost_job_probability",
    "days_active", "salary_max", "applicant_count", "date_first_seen",
    "activity_score", "competition_score",
}
LIST_OPTIONS = [
    selectinload(JobPosting.company),
    selectinload(JobPosting.skills),
    selectinload(JobPosting.source_sightings),
]
DETAIL_OPTIONS = LIST_OPTIONS + [selectinload(JobPosting.repost_events), selectinload(JobPosting.events)]
SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _filters(
    q=None, industry=None, job_family=None, job_board=None, classification=None, remote_type=None,
    seniority=None, employment_type=None, metro_area=None, salary_min=None,
    salary_max=None, ghost_max=None, health_min=None, active_hiring_min=None, applicant_max=None,
):
    values = [JobPosting.is_active.is_(True)]
    if q:
        search = q.strip()
        search_like = f"%{search}%"
        compact_search_like = f"%{search.replace(',', '').strip()}%"

        values.append(or_(
            JobPosting.title_raw.ilike(search_like),
            JobPosting.title_normalized.ilike(search_like),
            JobPosting.location_raw.ilike(search_like),
            JobPosting.location_raw.ilike(compact_search_like),
            JobPosting.metro_area.ilike(search_like),
            Company.name.ilike(search_like),
        ))
    if industry:
        values.append(JobPosting.industry == industry)
    if job_family:
        values.append(JobPosting.job_family == job_family)
    if job_board:
        board = job_board.strip()
        board_like = f"%{board}%"
        values.append(or_(
            JobPosting.source == board,
            JobPosting.publisher_name.ilike(board_like),
            JobPosting.collection_provider == board,
            JobPosting.source_sightings.any(or_(
                JobSourceSighting.source == board,
                JobSourceSighting.publisher_name.ilike(board_like),
                JobSourceSighting.collection_provider == board,
            )),
        ))
    if classification:
        values.append(JobPosting.listing_classification == classification)
    if remote_type:
        values.append(JobPosting.remote_type == remote_type)
    if seniority:
        values.append(JobPosting.seniority == seniority)
    if employment_type:
        values.append(JobPosting.employment_type == employment_type)
    if metro_area:
        values.append(JobPosting.metro_area.ilike(f"%{metro_area}%"))
    if salary_min is not None:
        values.append(JobPosting.salary_max >= salary_min)
    if salary_max is not None:
        values.append(JobPosting.salary_min <= salary_max)
    if ghost_max is not None:
        values.append(JobPosting.ghost_job_probability <= ghost_max)
    if health_min is not None:
        values.append(JobPosting.health_score >= health_min)
    if active_hiring_min is not None:
        values.append(JobPosting.active_hiring_confidence >= active_hiring_min)
    if applicant_max is not None:
        values.append(or_(
            JobPosting.applicant_count <= applicant_max,
            JobPosting.applicant_count.is_(None),
        ))
    return values


async def _serialize_jobs(
    jobs: list[JobPosting], db: AsyncSession, schema: type[SchemaT]
) -> list[SchemaT]:
    source_map = await load_canonical_sources(jobs, db)
    return [
        schema.model_validate(job).model_copy(
            update={"canonical_sources": source_map.get(canonical_group_id(job), [])}
        )
        for job in jobs
    ]


@router.get("/", response_model=PaginatedJobsResponse)
async def list_jobs(
    q: Optional[str] = None,
    industry: Optional[str] = None,
    job_family: Optional[str] = None,
    job_board: Optional[str] = None,
    classification: Optional[str] = None,
    remote_type: Optional[str] = None,
    seniority: Optional[str] = None,
    employment_type: Optional[str] = None,
    metro_area: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    ghost_max: Optional[float] = Query(None, ge=0, le=1),
    health_min: Optional[float] = Query(None, ge=0, le=100),
    active_hiring_min: Optional[float] = Query(None, ge=0, le=100),
    applicant_max: Optional[int] = Query(None, ge=0),
    collapse_canonical: bool = True,
    sort_by: str = "active_hiring_confidence",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    conditions = _filters(
        q, industry, job_family, job_board, classification, remote_type, seniority,
        employment_type, metro_area, salary_min, salary_max, ghost_max,
        health_min, active_hiring_min, applicant_max,
    )
    column = getattr(JobPosting, sort_by if sort_by in SORT_COLS else "active_hiring_confidence")
    order = asc(column).nulls_last() if sort_dir == "asc" else desc(column).nulls_last()

    if collapse_canonical:
        group_expr = func.coalesce(JobPosting.canonical_job_id, JobPosting.id)
        ranked = (
            select(
                JobPosting.id.label("job_id"),
                func.row_number().over(
                    partition_by=group_expr,
                    order_by=(
                        JobPosting.active_hiring_confidence.desc().nullslast(),
                        JobPosting.date_last_seen.desc(),
                        JobPosting.id.asc(),
                    ),
                ).label("group_rank"),
            )
            .join(Company)
            .where(*conditions)
            .subquery()
        )
        representative_ids = select(ranked.c.job_id).where(ranked.c.group_rank == 1)
        total = await db.scalar(
            select(func.count(func.distinct(group_expr)))
            .select_from(JobPosting)
            .join(Company)
            .where(*conditions)
        ) or 0
        base = select(JobPosting).where(JobPosting.id.in_(representative_ids))
    else:
        base = select(JobPosting).join(Company).where(*conditions)
        total = await db.scalar(
            select(func.count()).select_from(
                base.with_only_columns(JobPosting.id).order_by(None).subquery()
            )
        ) or 0

    jobs = list((await db.execute(
        base.options(*LIST_OPTIONS)
        .order_by(order, JobPosting.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().unique())
    results = await _serialize_jobs(jobs, db, JobPostingListItem)
    return PaginatedJobsResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
        results=results,
    )


@router.get("/stats", response_model=MarketStats)
async def market_stats(db: AsyncSession = Depends(get_db)):
    active = JobPosting.is_active.is_(True)
    total = await db.scalar(select(func.count(JobPosting.id)).where(active)) or 0
    scored = await db.scalar(select(func.count(JobPosting.id)).where(active, JobPosting.active_hiring_confidence.is_not(None))) or 0

    async def avg(column):
        value = await db.scalar(select(func.avg(column)).where(active))
        return float(value or 0)

    high_ghost = await db.scalar(select(func.count(JobPosting.id)).where(active, JobPosting.ghost_job_probability >= 0.60)) or 0
    total_apps = await db.scalar(select(func.sum(JobPosting.applicant_count)).where(active)) or 0
    classification_rows = (await db.execute(
        select(JobPosting.listing_classification, func.count(JobPosting.id)).where(active)
        .group_by(JobPosting.listing_classification).order_by(func.count(JobPosting.id).desc())
    )).all()
    industry_rows = (await db.execute(
        select(JobPosting.industry, func.count(JobPosting.id)).where(active, JobPosting.industry.is_not(None))
        .group_by(JobPosting.industry).order_by(func.count(JobPosting.id).desc()).limit(10)
    )).all()
    skill_rows = (await db.execute(
        select(JobSkill.skill, func.count(JobSkill.id)).join(JobPosting).where(active)
        .group_by(JobSkill.skill).order_by(func.count(JobSkill.id).desc()).limit(10)
    )).all()
    return MarketStats(
        total_active_jobs=total,
        scored_active_jobs=scored,
        avg_active_hiring_confidence=round(await avg(JobPosting.active_hiring_confidence), 1),
        avg_ghost_probability=round(await avg(JobPosting.ghost_job_probability), 3),
        avg_health_score=round(await avg(JobPosting.health_score), 1),
        high_ghost_risk_count=high_ghost,
        classification_counts=[{"classification": key, "count": count} for key, count in classification_rows],
        top_industries=[{"industry": key, "count": count} for key, count in industry_rows],
        top_skills=[{"skill": key, "count": count} for key, count in skill_rows],
        avg_days_active=round(await avg(JobPosting.days_active), 1),
        total_applicants=int(total_apps),
    )


@router.get("/{job_id}", response_model=JobPostingDetail)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(
        select(JobPosting).options(*DETAIL_OPTIONS).where(JobPosting.id == job_id)
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return (await _serialize_jobs([job], db, JobPostingDetail))[0]


@router.post("/{job_id}/score")
async def trigger_score(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(
        select(JobPosting).options(
            selectinload(JobPosting.company),
            selectinload(JobPosting.snapshots),
            selectinload(JobPosting.embedding),
        ).where(JobPosting.id == job_id)
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    scores = await ScoringService().score_job(job, db)
    await db.commit()
    return {"job_id": job_id, "scores": scores}
