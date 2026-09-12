from __future__ import annotations

import math
from datetime import timedelta
from typing import Annotated, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_optional_device_id, require_admin_key
from app.core.time import utc_now
from app.db.session import get_db
from app.models.models import Company, JobApplication, JobDismissal, JobFavorite, JobNote, JobPosting, JobSkill, JobSourceSighting
from app.schemas.jobs import ActiveHiringReasoningOut, JobPostingDetail, JobPostingListItem, MarketStats, PaginatedJobsResponse
from app.services.scoring import ScoringService
from app.services.source_attribution import canonical_group_id, load_canonical_sources, own_sources

router = APIRouter(prefix="/jobs", tags=["jobs"])
SortField = Literal[
    "active_hiring_confidence",
    "health_score",
    "ghost_job_probability",
    "days_active",
    "salary_max",
    "applicant_count",
    "date_first_seen",
    "date_posted",
    "activity_score",
    "competition_score",
]
SortDirection = Literal["asc", "desc"]

SORT_COLUMNS = {
    "active_hiring_confidence": JobPosting.active_hiring_confidence,
    "health_score": JobPosting.health_score,
    "ghost_job_probability": JobPosting.ghost_job_probability,
    "days_active": JobPosting.days_active,
    "salary_max": JobPosting.salary_max,
    "applicant_count": JobPosting.applicant_count,
    "date_first_seen": JobPosting.date_first_seen,
    "date_posted": JobPosting.date_posted,
    "activity_score": JobPosting.activity_score,
    "competition_score": JobPosting.competition_score,
}
LIST_OPTIONS = [
    selectinload(JobPosting.company),
    selectinload(JobPosting.skills),
    selectinload(JobPosting.source_sightings),
]
DETAIL_OPTIONS = LIST_OPTIONS + [selectinload(JobPosting.repost_events), selectinload(JobPosting.events)]
SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _has_specialization_tag(tag: str):
    """Match `tag` as one of the comma-joined values in JobPosting.specialization
    (e.g. "backend,security_clearance"), not merely as a substring."""
    return or_(
        JobPosting.specialization == tag,
        JobPosting.specialization.ilike(f"{tag},%"),
        JobPosting.specialization.ilike(f"%,{tag}"),
        JobPosting.specialization.ilike(f"%,{tag},%"),
    )


def _filters(
    q=None, industry=None, job_family=None, job_board=None, classification=None, remote_type=None,
    seniority=None, employment_type=None, metro_area=None, salary_min=None,
    salary_max=None, ghost_max=None, health_min=None, active_hiring_min=None, applicant_max=None,
    max_age_days=None, clearance_required=None, device_id=None,
):
    values = [JobPosting.is_active.is_(True)]
    if device_id:
        values.append(
            JobPosting.id.not_in(
                select(JobDismissal.job_posting_id).where(JobDismissal.device_id == device_id)
            )
        )
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
    if max_age_days is not None:
        cutoff = utc_now() - timedelta(days=max_age_days)
        values.append(or_(
            JobPosting.date_posted >= cutoff,
            and_(
                JobPosting.date_posted.is_(None),
                JobPosting.date_first_seen >= cutoff,
            ),
        ))
    if clearance_required is not None:
        has_clearance = _has_specialization_tag("security_clearance")
        values.append(has_clearance if clearance_required else or_(
            JobPosting.specialization.is_(None), ~has_clearance,
        ))
    return values


async def _serialize_jobs(
    jobs: list[JobPosting],
    db: AsyncSession,
    schema: type[SchemaT],
    *,
    collapse: bool = True,
    max_age_days: int | None = None,
    device_id: str | None = None,
) -> list[SchemaT]:
    if collapse:
        source_map = await load_canonical_sources(
            jobs,
            db,
            max_age_days=max_age_days,
        )
        sources_by_job = {job.id: source_map.get(canonical_group_id(job), []) for job in jobs}
    else:
        sources_by_job = {job.id: own_sources(job) for job in jobs}

    favorited_ids: set[int] = set()
    applied_ids: set[int] = set()
    notes_by_job: dict[int, str] = {}
    if device_id and jobs:
        job_ids = [job.id for job in jobs]
        favorited_ids = set((await db.execute(
            select(JobFavorite.job_posting_id).where(
                JobFavorite.device_id == device_id, JobFavorite.job_posting_id.in_(job_ids)
            )
        )).scalars())
        applied_ids = set((await db.execute(
            select(JobApplication.job_posting_id).where(
                JobApplication.device_id == device_id, JobApplication.job_posting_id.in_(job_ids)
            )
        )).scalars())
        notes_by_job = dict((await db.execute(
            select(JobNote.job_posting_id, JobNote.note).where(
                JobNote.device_id == device_id, JobNote.job_posting_id.in_(job_ids)
            )
        )).all())

    serialized: list[SchemaT] = []
    for job in jobs:
        canonical_sources = sources_by_job.get(job.id, [])
        reasoning_data = ScoringService.active_hiring_reasoning(
            job,
            source_count=len(canonical_sources),
        )
        reasoning = (
            ActiveHiringReasoningOut.model_validate(reasoning_data)
            if reasoning_data is not None
            else None
        )
        serialized.append(
            schema.model_validate(job).model_copy(
                update={
                    "canonical_sources": canonical_sources,
                    "active_hiring_reasoning": reasoning,
                    "is_favorited": job.id in favorited_ids,
                    "is_applied": job.id in applied_ids,
                    "note": notes_by_job.get(job.id),
                }
            )
        )
    return serialized


@router.get("/", response_model=PaginatedJobsResponse)
async def list_jobs(
    q: Annotated[str | None, Query(max_length=100)] = None,
    industry: Annotated[str | None, Query(max_length=100)] = None,
    job_family: Annotated[str | None, Query(max_length=100)] = None,
    job_board: Annotated[str | None, Query(max_length=100)] = None,
    classification: Literal["original", "parallel", "repost"] | None = None,
    remote_type: Literal["Remote", "Hybrid", "Onsite"] | None = None,
    seniority: Literal["Entry", "Mid", "Senior", "Lead", "Executive"] | None = None,
    employment_type: Literal["Full-time", "Part-time", "Contract", "Internship"] | None = None,
    metro_area: Annotated[str | None, Query(max_length=100)] = None,
    salary_min: Annotated[int | None, Query(ge=0, le=10_000_000)] = None,
    salary_max: Annotated[int | None, Query(ge=0, le=10_000_000)] = None,
    ghost_max: Annotated[float | None, Query(ge=0, le=1)] = None,
    health_min: Annotated[float | None, Query(ge=0, le=100)] = None,
    active_hiring_min: Annotated[float | None, Query(ge=0, le=100)] = None,
    applicant_max: Annotated[int | None, Query(ge=0, le=1_000_000)] = None,
    max_age_days: Annotated[int | None, Query(ge=1, le=3650)] = None,
    clearance_required: bool | None = None,
    collapse_canonical: bool = True,
    sort_by: SortField = "active_hiring_confidence",
    sort_dir: SortDirection = "desc",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    db: AsyncSession = Depends(get_db),
    device_id: Annotated[str | None, Depends(get_optional_device_id)] = None,
):
    conditions = _filters(
        q, industry, job_family, job_board, classification, remote_type, seniority,
        employment_type, metro_area, salary_min, salary_max, ghost_max,
        health_min, active_hiring_min, applicant_max, max_age_days, clearance_required,
        device_id,
    )
    column = SORT_COLUMNS[sort_by]
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
    results = await _serialize_jobs(
        jobs,
        db,
        JobPostingListItem,
        collapse=collapse_canonical,
        max_age_days=max_age_days,
        device_id=device_id,
    )
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

    # All scalar aggregates in one round trip: func.count(column) (as opposed
    # to func.count(id)) already skips NULLs, which is exactly "scored"
    # (active_hiring_confidence IS NOT NULL); the FILTER clause folds the
    # high-ghost-risk count in too, so this single query replaces what were
    # six separate ones.
    total, scored, avg_confidence, avg_ghost, avg_health, avg_days, high_ghost, total_apps = (await db.execute(
        select(
            func.count(JobPosting.id),
            func.count(JobPosting.active_hiring_confidence),
            func.avg(JobPosting.active_hiring_confidence),
            func.avg(JobPosting.ghost_job_probability),
            func.avg(JobPosting.health_score),
            func.avg(JobPosting.days_active),
            func.count(JobPosting.id).filter(JobPosting.ghost_job_probability >= 0.60),
            func.sum(JobPosting.applicant_count),
        ).where(active)
    )).one()

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
        total_active_jobs=total or 0,
        scored_active_jobs=scored or 0,
        avg_active_hiring_confidence=round(float(avg_confidence or 0), 1),
        avg_ghost_probability=round(float(avg_ghost or 0), 3),
        avg_health_score=round(float(avg_health or 0), 1),
        high_ghost_risk_count=high_ghost or 0,
        classification_counts=[{"classification": key, "count": count} for key, count in classification_rows],
        top_industries=[{"industry": key, "count": count} for key, count in industry_rows],
        top_skills=[{"skill": key, "count": count} for key, count in skill_rows],
        avg_days_active=round(float(avg_days or 0), 1),
        total_applicants=int(total_apps or 0),
    )


@router.get("/{job_id}", response_model=JobPostingDetail)
async def get_job(
    job_id: Annotated[int, Path(ge=1)],
    max_age_days: Annotated[int | None, Query(ge=1)] = None,
    db: AsyncSession = Depends(get_db),
    device_id: Annotated[str | None, Depends(get_optional_device_id)] = None,
):
    job = (await db.execute(
        select(JobPosting).options(*DETAIL_OPTIONS).where(JobPosting.id == job_id)
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return (await _serialize_jobs(
        [job],
        db,
        JobPostingDetail,
        max_age_days=max_age_days,
        device_id=device_id,
    ))[0]


@router.get("/{job_id}/related", response_model=list[JobPostingListItem])
async def related_jobs(
    job_id: Annotated[int, Path(ge=1)],
    db: AsyncSession = Depends(get_db),
    device_id: Annotated[str | None, Depends(get_optional_device_id)] = None,
):
    """Other active listings in job_id's canonical group -- the same-employer,
    same-time openings behind the "Related openings" score signal
    (classification == "parallel"; see ScoringService.active_hiring_reasoning).
    Canonical grouping already treats these as one real-world-adjacent group
    (job.canonical_job_id is set for parallel siblings the same way it is for
    reposts), so membership is exactly coalesce(canonical_job_id, id).
    """
    job = (await db.execute(
        select(JobPosting.id, JobPosting.canonical_job_id).where(JobPosting.id == job_id)
    )).first()
    if not job:
        raise HTTPException(404, "Job not found")

    group_id = job.canonical_job_id or job.id
    group_expr = func.coalesce(JobPosting.canonical_job_id, JobPosting.id)
    conditions = [
        group_expr == group_id,
        JobPosting.id != job_id,
        JobPosting.is_active.is_(True),
    ]
    if device_id:
        conditions.append(
            JobPosting.id.not_in(
                select(JobDismissal.job_posting_id).where(JobDismissal.device_id == device_id)
            )
        )

    siblings = list((await db.execute(
        select(JobPosting)
        .options(*LIST_OPTIONS)
        .where(*conditions)
        .order_by(JobPosting.active_hiring_confidence.desc().nullslast(), JobPosting.date_last_seen.desc())
        .limit(25)
    )).scalars().unique())

    # False by construction (own group, excludes job_id), so each sibling's
    # "Found on" should list only its own sources, not the whole group's --
    # collapse=True would instead re-merge every sibling back into a single
    # representative, which is exactly what this endpoint exists to avoid.
    return await _serialize_jobs(siblings, db, JobPostingListItem, collapse=False, device_id=device_id)


@router.post(
    "/{job_id}/score",
    dependencies=[Depends(require_admin_key)],
)
async def trigger_score(
    job_id: Annotated[int, Path(ge=1)],
    db: AsyncSession = Depends(get_db),
):
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
