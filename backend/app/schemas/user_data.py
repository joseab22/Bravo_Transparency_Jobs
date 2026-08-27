from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.jobs import JobPostingListItem


class FavoriteOut(BaseModel):
    job_posting_id: int
    created_at: datetime
    job: JobPostingListItem


class ApplicationIn(BaseModel):
    status: str = Field(pattern="^(applied|interviewing|offer|rejected|withdrawn)$")
    applied_date: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("applied_date")
    @classmethod
    def _naive_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        # DB columns are naive UTC by convention (see app.core.time.utc_now).
        # A client-supplied ISO string (e.g. JS Date.toISOString(), which ends
        # in "Z") parses as timezone-aware, and asyncpg rejects binding that
        # into a TIMESTAMP WITHOUT TIME ZONE column outright.
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


class ApplicationOut(BaseModel):
    job_posting_id: int
    status: str
    applied_date: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    job: JobPostingListItem


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=5000)


class NoteOut(BaseModel):
    job_posting_id: int
    # note is the standalone note (Notes tab, editable here). application_note
    # is read-only in this context -- it mirrors JobApplication.notes so a job
    # with both shows consolidated in one row, but it is only ever written via
    # the Applications tab/endpoint, never here.
    note: Optional[str] = None
    application_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    job: JobPostingListItem


class RecentlyViewedOut(BaseModel):
    job_posting_id: int
    viewed_at: datetime
    job: JobPostingListItem


class DismissalOut(BaseModel):
    job_posting_id: int
    created_at: datetime
    job: JobPostingListItem


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    filters: dict = Field(default_factory=dict)


class SavedSearchOut(BaseModel):
    id: int
    name: str
    filters: dict
    created_at: datetime
