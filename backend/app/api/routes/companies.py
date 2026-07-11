from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import Company, JobPosting
from app.schemas.jobs import CompanyOut, JobPostingListItem
from app.services.source_attribution import canonical_group_id, load_canonical_sources

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyOut])
async def list_companies(
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Company).order_by(Company.hiring_intensity.desc().nullslast(), Company.name)
    if q:
        query = query.where(Company.name.ilike(f"%{q}%"))
    return list((await db.execute(query.limit(limit))).scalars())


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    return company


@router.get("/{company_id}/jobs", response_model=list[JobPostingListItem])
async def company_jobs(
    company_id: int,
    active_only: bool = True,
    collapse_canonical: bool = True,
    db: AsyncSession = Depends(get_db),
):
    query = select(JobPosting).options(
        selectinload(JobPosting.company),
        selectinload(JobPosting.skills),
        selectinload(JobPosting.source_sightings),
    ).where(JobPosting.company_id == company_id)
    if active_only:
        query = query.where(JobPosting.is_active.is_(True))
    jobs = list((await db.execute(
        query.order_by(
            JobPosting.active_hiring_confidence.desc().nullslast(),
            JobPosting.date_last_seen.desc(),
        )
    )).scalars().unique())

    if collapse_canonical:
        representatives: dict[int, JobPosting] = {}
        for job in jobs:
            representatives.setdefault(canonical_group_id(job), job)
        jobs = list(representatives.values())

    source_map = await load_canonical_sources(jobs, db)
    return [
        JobPostingListItem.model_validate(job).model_copy(
            update={"canonical_sources": source_map.get(canonical_group_id(job), [])}
        )
        for job in jobs
    ]
