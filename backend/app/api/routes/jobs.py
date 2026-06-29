from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from typing import Optional
import math

from app.db.session import get_db
from app.models.models import JobPosting, Company
from app.schemas.jobs import (
    JobPostingListItem, JobPostingDetail,
    PaginatedJobsResponse, MarketStats,
)
from app.services.scoring import ScoringService

router = APIRouter(prefix="/jobs", tags=["jobs"])

SORT_COLS = {
    "health_score", "ghost_job_probability", "days_active",
    "salary_max", "applicant_count", "date_first_seen",
    "activity_score", "competition_score",
}

# Eager-load options for list view (avoids async lazy-load MissingGreenlet errors)
LIST_OPTIONS = [
    selectinload(JobPosting.company),
    selectinload(JobPosting.skills),
    selectinload(JobPosting.source_sightings),
]

# Eager-load options for detail view (loads everything)
DETAIL_OPTIONS = LIST_OPTIONS + [
    selectinload(JobPosting.repost_events),
    selectinload(JobPosting.events),
]


def _build_query(
    q=None, industry=None, remote_type=None, seniority=None,
    employment_type=None, metro_area=None, salary_min=None, salary_max=None,
    ghost_max=None, health_min=None, sort_by="health_score", sort_dir="desc",
):
    query = (
        select(JobPosting)
        .options(*LIST_OPTIONS)
        .where(JobPosting.is_active == True)
    )
    if q:
        ql = f"%{q.lower()}%"
        query = query.join(JobPosting.company).where(or_(
            JobPosting.title_normalized.ilike(ql),
            Company.name.ilike(ql),
        ))
    if industry:
        query = query.where(JobPosting.industry == industry)
    if remote_type:
        query = query.where(JobPosting.remote_type == remote_type)
    if seniority:
        query = query.where(JobPosting.seniority == seniority)
    if employment_type:
        query = query.where(JobPosting.employment_type == employment_type)
    if metro_area:
        query = query.where(JobPosting.metro_area.ilike(f"%{metro_area}%"))
    if salary_min:
        query = query.where(JobPosting.salary_max >= salary_min)
    if salary_max:
        query = query.where(JobPosting.salary_min <= salary_max)
    if ghost_max is not None:
        query = query.where(JobPosting.ghost_job_probability <= ghost_max)
    if health_min is not None:
        query = query.where(JobPosting.health_score >= health_min)

    col_name = sort_by if sort_by in SORT_COLS else "health_score"
    col = getattr(JobPosting, col_name, JobPosting.health_score)
    query = query.order_by(asc(col) if sort_dir == "asc" else desc(col))
    return query


@router.get("/", response_model=PaginatedJobsResponse)
async def list_jobs(
    q: Optional[str] = None,
    industry: Optional[str] = None,
    remote_type: Optional[str] = None,
    seniority: Optional[str] = None,
    employment_type: Optional[str] = None,
    metro_area: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    ghost_max: Optional[float] = None,
    health_min: Optional[float] = None,
    sort_by: str = "health_score",
    sort_dir: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = _build_query(
        q=q, industry=industry, remote_type=remote_type, seniority=seniority,
        employment_type=employment_type, metro_area=metro_area,
        salary_min=salary_min, salary_max=salary_max,
        ghost_max=ghost_max, health_min=health_min,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    # Count without options (faster)
    count_q = select(func.count()).select_from(
        select(JobPosting).where(JobPosting.is_active == True).subquery()
    )
    total = (await db.execute(count_q)).scalar_one()
    jobs_result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    jobs = jobs_result.scalars().unique().all()
    return PaginatedJobsResponse(
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
        results=jobs,
    )


@router.get("/stats", response_model=MarketStats)
async def market_stats(db: AsyncSession = Depends(get_db)):
    active = JobPosting.is_active == True
    total = (await db.execute(select(func.count(JobPosting.id)).where(active))).scalar_one()
    avg_ghost = (await db.execute(select(func.avg(JobPosting.ghost_job_probability)).where(active))).scalar_one() or 0
    avg_health = (await db.execute(select(func.avg(JobPosting.health_score)).where(active))).scalar_one() or 0
    high_ghost = (await db.execute(select(func.count(JobPosting.id)).where(
        and_(active, JobPosting.ghost_job_probability >= 0.60)))).scalar_one()
    avg_days = (await db.execute(select(func.avg(JobPosting.days_active)).where(active))).scalar_one() or 0
    total_apps = (await db.execute(select(func.sum(JobPosting.applicant_count)).where(active))).scalar_one() or 0
    return MarketStats(
        total_active_jobs=total,
        avg_ghost_probability=round(float(avg_ghost), 3),
        avg_health_score=round(float(avg_health), 1),
        high_ghost_risk_count=high_ghost,
        top_industries=[], top_skills=[],
        avg_days_active=round(float(avg_days), 1),
        total_applicants=int(total_apps),
    )


@router.get("/{job_id}", response_model=JobPostingDetail)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobPosting)
        .options(*DETAIL_OPTIONS)
        .where(JobPosting.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/score")
async def trigger_score(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobPosting).options(*LIST_OPTIONS).where(JobPosting.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    scorer = ScoringService()
    scores = await scorer.score_job(job, db)
    await db.commit()
    return {"job_id": job_id, "scores": scores}
