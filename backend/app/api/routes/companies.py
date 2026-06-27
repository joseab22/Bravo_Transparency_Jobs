from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.db.session import get_db
from app.models.models import Company, JobPosting
from app.schemas.jobs import CompanyOut

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyOut])
async def list_companies(
    q: Optional[str] = None,
    industry: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Company)
    if q:
        query = query.where(Company.name.ilike(f"%{q}%"))
    if industry:
        query = query.where(Company.industry == industry)

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/{company_id}/jobs")
async def get_company_jobs(
    company_id: int,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    query = select(JobPosting).where(JobPosting.company_id == company_id)
    if active_only:
        query = query.where(JobPosting.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()
