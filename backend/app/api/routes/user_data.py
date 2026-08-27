from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.jobs import LIST_OPTIONS, _serialize_jobs
from app.core.security import get_device_id
from app.core.time import utc_now
from app.db.session import get_db
from app.models.models import (
    JobApplication, JobDismissal, JobFavorite, JobNote, JobPosting, JobView, SavedSearch,
)
from app.schemas.jobs import JobPostingListItem
from app.schemas.user_data import (
    ApplicationIn,
    ApplicationOut,
    DismissalOut,
    FavoriteOut,
    NoteIn,
    NoteOut,
    RecentlyViewedOut,
    SavedSearchIn,
    SavedSearchOut,
)

router = APIRouter(prefix="/me", tags=["user-data"])

DeviceId = Annotated[str, Depends(get_device_id)]


async def _get_job_or_404(job_id: int, db: AsyncSession) -> JobPosting:
    job = (await db.execute(
        select(JobPosting).options(*LIST_OPTIONS).where(JobPosting.id == job_id)
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


async def _serialize_one(job: JobPosting, db: AsyncSession, device_id: str) -> JobPostingListItem:
    return (await _serialize_jobs([job], db, JobPostingListItem, device_id=device_id))[0]


async def _serialize_by_job_id(
    job_posting_ids: list[int], db: AsyncSession, device_id: str
) -> dict[int, JobPostingListItem]:
    if not job_posting_ids:
        return {}
    jobs = list((await db.execute(
        select(JobPosting).options(*LIST_OPTIONS).where(JobPosting.id.in_(job_posting_ids))
    )).scalars().unique())
    serialized = await _serialize_jobs(jobs, db, JobPostingListItem, device_id=device_id)
    return {item.id: item for item in serialized}


# --- Favorites ---------------------------------------------------------

@router.get("/favorites", response_model=list[FavoriteOut])
async def list_favorites(device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    rows = list((await db.execute(
        select(JobFavorite).where(JobFavorite.device_id == device_id)
        .order_by(JobFavorite.created_at.desc())
    )).scalars())
    jobs_by_id = await _serialize_by_job_id([row.job_posting_id for row in rows], db, device_id)
    return [
        FavoriteOut(job_posting_id=row.job_posting_id, created_at=row.created_at, job=jobs_by_id[row.job_posting_id])
        for row in rows if row.job_posting_id in jobs_by_id
    ]


@router.post("/favorites/{job_id}", response_model=FavoriteOut, status_code=201)
async def add_favorite(
    job_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    job = await _get_job_or_404(job_id, db)
    existing = (await db.execute(
        select(JobFavorite).where(JobFavorite.device_id == device_id, JobFavorite.job_posting_id == job_id)
    )).scalar_one_or_none()
    if not existing:
        existing = JobFavorite(device_id=device_id, job_posting_id=job_id)
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
    return FavoriteOut(job_posting_id=job_id, created_at=existing.created_at, job=await _serialize_one(job, db, device_id))


@router.delete("/favorites/{job_id}", status_code=204)
async def remove_favorite(
    job_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    await db.execute(
        delete(JobFavorite).where(JobFavorite.device_id == device_id, JobFavorite.job_posting_id == job_id)
    )
    await db.commit()


# --- Applications --------------------------------------------------------

@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    rows = list((await db.execute(
        select(JobApplication).where(JobApplication.device_id == device_id)
        .order_by(JobApplication.updated_at.desc())
    )).scalars())
    jobs_by_id = await _serialize_by_job_id([row.job_posting_id for row in rows], db, device_id)
    return [
        ApplicationOut(
            job_posting_id=row.job_posting_id, status=row.status, applied_date=row.applied_date,
            notes=row.notes, created_at=row.created_at, updated_at=row.updated_at,
            job=jobs_by_id[row.job_posting_id],
        )
        for row in rows if row.job_posting_id in jobs_by_id
    ]


@router.put("/applications/{job_id}", response_model=ApplicationOut)
async def upsert_application(
    job_id: Annotated[int, Path(ge=1)],
    payload: ApplicationIn,
    device_id: DeviceId,
    db: AsyncSession = Depends(get_db),
):
    job = await _get_job_or_404(job_id, db)
    existing = (await db.execute(
        select(JobApplication).where(JobApplication.device_id == device_id, JobApplication.job_posting_id == job_id)
    )).scalar_one_or_none()
    if existing:
        existing.status = payload.status
        existing.applied_date = payload.applied_date
        existing.notes = payload.notes
    else:
        existing = JobApplication(
            device_id=device_id, job_posting_id=job_id, status=payload.status,
            applied_date=payload.applied_date, notes=payload.notes,
        )
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return ApplicationOut(
        job_posting_id=job_id, status=existing.status, applied_date=existing.applied_date,
        notes=existing.notes, created_at=existing.created_at, updated_at=existing.updated_at,
        job=await _serialize_one(job, db, device_id),
    )


@router.delete("/applications/{job_id}", status_code=204)
async def remove_application(
    job_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    await db.execute(
        delete(JobApplication).where(JobApplication.device_id == device_id, JobApplication.job_posting_id == job_id)
    )
    await db.commit()


# --- Notes ---------------------------------------------------------------

async def _application_notes_by_job(
    job_posting_ids: list[int], device_id: str, db: AsyncSession
) -> dict[int, JobApplication]:
    if not job_posting_ids:
        return {}
    rows = list((await db.execute(
        select(JobApplication).where(
            JobApplication.device_id == device_id,
            JobApplication.job_posting_id.in_(job_posting_ids),
            JobApplication.notes.is_not(None),
            JobApplication.notes != "",
        )
    )).scalars())
    return {row.job_posting_id: row for row in rows}


@router.get("/notes", response_model=list[NoteOut])
async def list_notes(device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    # Consolidates two distinct note sources into one row per job: standalone
    # notes (JobNote, editable here) and application notes (JobApplication.notes,
    # editable only from the Applications tab). A job with only an application
    # note still belongs in this list -- it's a note the user wrote, even
    # though it lives in the applications table.
    note_rows = list((await db.execute(
        select(JobNote).where(JobNote.device_id == device_id)
    )).scalars())
    notes_by_job = {row.job_posting_id: row for row in note_rows}

    app_rows = list((await db.execute(
        select(JobApplication).where(
            JobApplication.device_id == device_id,
            JobApplication.notes.is_not(None),
            JobApplication.notes != "",
        )
    )).scalars())
    app_notes_by_job = {row.job_posting_id: row for row in app_rows}

    job_ids = list(set(notes_by_job) | set(app_notes_by_job))
    jobs_by_id = await _serialize_by_job_id(job_ids, db, device_id)

    entries = [
        NoteOut(
            job_posting_id=job_id,
            note=notes_by_job[job_id].note if job_id in notes_by_job else None,
            application_note=app_notes_by_job[job_id].notes if job_id in app_notes_by_job else None,
            created_at=notes_by_job[job_id].created_at if job_id in notes_by_job else None,
            updated_at=(
                notes_by_job[job_id].updated_at if job_id in notes_by_job
                else app_notes_by_job[job_id].updated_at
            ),
            job=jobs_by_id[job_id],
        )
        for job_id in job_ids
        if job_id in jobs_by_id
    ]
    entries.sort(key=lambda entry: entry.updated_at or datetime.min, reverse=True)
    return entries


@router.put("/notes/{job_id}", response_model=NoteOut)
async def upsert_note(
    job_id: Annotated[int, Path(ge=1)], payload: NoteIn, device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    job = await _get_job_or_404(job_id, db)
    existing = (await db.execute(
        select(JobNote).where(JobNote.device_id == device_id, JobNote.job_posting_id == job_id)
    )).scalar_one_or_none()
    if existing:
        existing.note = payload.note
    else:
        existing = JobNote(device_id=device_id, job_posting_id=job_id, note=payload.note)
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    application_notes = await _application_notes_by_job([job_id], device_id, db)
    application = application_notes.get(job_id)
    return NoteOut(
        job_posting_id=job_id, note=existing.note,
        application_note=application.notes if application else None,
        created_at=existing.created_at,
        updated_at=existing.updated_at, job=await _serialize_one(job, db, device_id),
    )


@router.delete("/notes/{job_id}", status_code=204)
async def remove_note(
    job_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    await db.execute(delete(JobNote).where(JobNote.device_id == device_id, JobNote.job_posting_id == job_id))
    await db.commit()


# --- Recently viewed -------------------------------------------------------

@router.post("/views/{job_id}", status_code=204)
async def record_view(
    job_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    await _get_job_or_404(job_id, db)
    existing = (await db.execute(
        select(JobView).where(JobView.device_id == device_id, JobView.job_posting_id == job_id)
    )).scalar_one_or_none()
    if existing:
        existing.viewed_at = utc_now()
    else:
        db.add(JobView(device_id=device_id, job_posting_id=job_id))
    await db.commit()


@router.get("/recently-viewed", response_model=list[RecentlyViewedOut])
async def list_recently_viewed(device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    rows = list((await db.execute(
        select(JobView).where(JobView.device_id == device_id).order_by(JobView.viewed_at.desc()).limit(50)
    )).scalars())
    jobs_by_id = await _serialize_by_job_id([row.job_posting_id for row in rows], db, device_id)
    return [
        RecentlyViewedOut(job_posting_id=row.job_posting_id, viewed_at=row.viewed_at, job=jobs_by_id[row.job_posting_id])
        for row in rows if row.job_posting_id in jobs_by_id
    ]


@router.delete("/recently-viewed", status_code=204)
async def clear_recently_viewed(device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(JobView).where(JobView.device_id == device_id))
    await db.commit()


# --- Hidden / dismissed ----------------------------------------------------

@router.post("/hidden/{job_id}", status_code=204)
async def dismiss_job(
    job_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    await _get_job_or_404(job_id, db)
    existing = (await db.execute(
        select(JobDismissal).where(JobDismissal.device_id == device_id, JobDismissal.job_posting_id == job_id)
    )).scalar_one_or_none()
    if not existing:
        db.add(JobDismissal(device_id=device_id, job_posting_id=job_id))
        await db.commit()


@router.delete("/hidden/{job_id}", status_code=204)
async def undismiss_job(
    job_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    await db.execute(
        delete(JobDismissal).where(JobDismissal.device_id == device_id, JobDismissal.job_posting_id == job_id)
    )
    await db.commit()


@router.get("/hidden", response_model=list[DismissalOut])
async def list_hidden(device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    rows = list((await db.execute(
        select(JobDismissal).where(JobDismissal.device_id == device_id).order_by(JobDismissal.created_at.desc())
    )).scalars())
    jobs_by_id = await _serialize_by_job_id([row.job_posting_id for row in rows], db, device_id)
    return [
        DismissalOut(job_posting_id=row.job_posting_id, created_at=row.created_at, job=jobs_by_id[row.job_posting_id])
        for row in rows if row.job_posting_id in jobs_by_id
    ]


# --- Saved searches ---------------------------------------------------------

@router.get("/saved-searches", response_model=list[SavedSearchOut])
async def list_saved_searches(device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    rows = list((await db.execute(
        select(SavedSearch).where(SavedSearch.device_id == device_id)
        .order_by(SavedSearch.created_at.desc())
    )).scalars())
    return [
        SavedSearchOut(id=row.id, name=row.name, filters=row.filters, created_at=row.created_at)
        for row in rows
    ]


@router.post("/saved-searches", response_model=SavedSearchOut, status_code=201)
async def save_search(payload: SavedSearchIn, device_id: DeviceId, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(
        select(SavedSearch).where(SavedSearch.device_id == device_id, SavedSearch.name == payload.name)
    )).scalar_one_or_none()
    if existing:
        existing.filters = payload.filters
    else:
        existing = SavedSearch(device_id=device_id, name=payload.name, filters=payload.filters)
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return SavedSearchOut(id=existing.id, name=existing.name, filters=existing.filters, created_at=existing.created_at)


@router.delete("/saved-searches/{search_id}", status_code=204)
async def remove_saved_search(
    search_id: Annotated[int, Path(ge=1)], device_id: DeviceId, db: AsyncSession = Depends(get_db)
):
    await db.execute(
        delete(SavedSearch).where(SavedSearch.device_id == device_id, SavedSearch.id == search_id)
    )
    await db.commit()
