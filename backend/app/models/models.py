from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class RemoteType(str, enum.Enum):
    remote = "Remote"
    hybrid = "Hybrid"
    onsite = "Onsite"


class SeniorityLevel(str, enum.Enum):
    entry = "Entry"
    mid = "Mid"
    senior = "Senior"
    lead = "Lead"
    executive = "Executive"


class EmploymentType(str, enum.Enum):
    full_time = "Full-time"
    part_time = "Part-time"
    contract = "Contract"
    internship = "Internship"


class JobSource(str, enum.Enum):
    linkedin = "linkedin"
    indeed = "indeed"
    glassdoor = "glassdoor"
    ziprecruiter = "ziprecruiter"
    dice = "dice"
    monster = "monster"
    simplify = "simplify"
    jobright = "jobright"
    jsearch = "jsearch"
    company_site = "company_site"


class EventType(str, enum.Enum):
    created = "created"
    reposted = "reposted"
    applicant_spike = "applicant_spike"
    salary_changed = "salary_changed"
    title_changed = "title_changed"
    description_changed = "description_changed"
    location_changed = "location_changed"
    expired = "expired"
    reactivated = "reactivated"
    source_added = "source_added"
    ghost_flagged = "ghost_flagged"


class ApplicationStatus(str, enum.Enum):
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    glassdoor_rating: Mapped[Optional[float]] = mapped_column(Float)
    glassdoor_url: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    turnover_score: Mapped[Optional[float]] = mapped_column(Float)
    hiring_intensity: Mapped[Optional[float]] = mapped_column(Float)
    ghost_job_rate: Mapped[Optional[float]] = mapped_column(Float)
    avg_reposts: Mapped[Optional[float]] = mapped_column(Float)
    median_time_to_fill: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    job_postings: Mapped[List["JobPosting"]] = relationship(back_populates="company", lazy="selectin")

    __table_args__ = (UniqueConstraint("name_normalized", name="uq_companies_name_normalized"),)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)

    job_identity_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    identity_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    canonical_job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), index=True
    )
    listing_classification: Mapped[str] = mapped_column(String(30), default="original", nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    publisher_name: Mapped[Optional[str]] = mapped_column(String(255))
    collection_provider: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))

    title_raw: Mapped[str] = mapped_column(String(500), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    job_family: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    specialization: Mapped[Optional[str]] = mapped_column(String(300))
    title_parse_confidence: Mapped[Optional[float]] = mapped_column(Float)

    location_raw: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(200))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100), default="US")
    metro_area: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    remote_type: Mapped[Optional[str]] = mapped_column(String(50))

    seniority: Mapped[Optional[str]] = mapped_column(String(50))
    employment_type: Mapped[Optional[str]] = mapped_column(String(50))
    department: Mapped[Optional[str]] = mapped_column(String(200))
    industry: Mapped[Optional[str]] = mapped_column(String(200))

    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD")
    salary_listed: Mapped[bool] = mapped_column(Boolean, default=False)

    education_required: Mapped[Optional[str]] = mapped_column(String(200))
    experience_years_min: Mapped[Optional[int]] = mapped_column(Integer)
    experience_years_max: Mapped[Optional[int]] = mapped_column(Integer)
    description_raw: Mapped[Optional[str]] = mapped_column(Text)

    date_posted: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    date_first_seen: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    date_last_seen: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    days_active: Mapped[int] = mapped_column(Integer, default=0)
    applicant_count: Mapped[Optional[int]] = mapped_column(Integer)

    ghost_job_probability: Mapped[Optional[float]] = mapped_column(Float)
    ghost_confidence: Mapped[Optional[float]] = mapped_column(Float)
    health_score: Mapped[Optional[float]] = mapped_column(Float)
    competition_score: Mapped[Optional[float]] = mapped_column(Float)
    interview_opportunity_score: Mapped[Optional[float]] = mapped_column(Float)
    salary_fairness_score: Mapped[Optional[float]] = mapped_column(Float)
    market_salary: Mapped[Optional[int]] = mapped_column(Integer)
    stability_score: Mapped[Optional[float]] = mapped_column(Float)
    activity_score: Mapped[Optional[float]] = mapped_column(Float)
    active_hiring_confidence: Mapped[Optional[float]] = mapped_column(Float)
    description_change_score: Mapped[Optional[float]] = mapped_column(Float)
    applicant_trend: Mapped[Optional[float]] = mapped_column(Float)
    salary_trend: Mapped[Optional[float]] = mapped_column(Float)
    repost_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    company: Mapped["Company"] = relationship(back_populates="job_postings", lazy="selectin")
    canonical_job: Mapped[Optional["JobPosting"]] = relationship(
        remote_side="JobPosting.id", foreign_keys=[canonical_job_id], post_update=True, lazy="selectin"
    )
    skills: Mapped[List["JobSkill"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    snapshots: Mapped[List["JobSnapshot"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    repost_events: Mapped[List["RepostEvent"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    source_sightings: Mapped[List["JobSourceSighting"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    events: Mapped[List["JobEvent"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    embedding: Mapped[Optional["JobEmbedding"]] = relationship(back_populates="job_posting", uselist=False, cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("ix_job_postings_identity_active", "job_identity_key", "is_active"),
        Index("ix_job_postings_fingerprint_active", "identity_fingerprint", "is_active"),
        Index("ix_job_postings_source_external", "source", "external_id"),
        Index("ix_job_postings_provider_external", "collection_provider", "external_id"),
    )


class JobSnapshot(Base):
    __tablename__ = "job_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    applicant_count: Mapped[Optional[int]] = mapped_column(Integer)
    description_raw: Mapped[Optional[str]] = mapped_column(Text)
    description_hash: Mapped[Optional[str]] = mapped_column(String(64))
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    title_raw: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    job_posting: Mapped["JobPosting"] = relationship(back_populates="snapshots")


class JobEvent(Base):
    __tablename__ = "job_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    job_posting: Mapped["JobPosting"] = relationship(back_populates="events")


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, unique=True)
    vector: Mapped[List[float]] = mapped_column(Vector(384), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), default="all-MiniLM-L6-v2")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    job_posting: Mapped["JobPosting"] = relationship(back_populates="embedding")
    __table_args__ = (Index("ix_job_embeddings_vector", "vector", postgresql_using="ivfflat", postgresql_with={"lists": 100}),)


class JobSkill(Base):
    __tablename__ = "job_skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    skill: Mapped[str] = mapped_column(String(200), nullable=False)
    skill_normalized: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    skill_category: Mapped[Optional[str]] = mapped_column(String(100))
    job_posting: Mapped["JobPosting"] = relationship(back_populates="skills")
    __table_args__ = (UniqueConstraint("job_posting_id", "skill_normalized", name="uq_job_skills"),)


class RepostEvent(Base):
    __tablename__ = "repost_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    job_identity_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    occurrence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    days_since_previous: Mapped[Optional[int]] = mapped_column(Integer)
    job_posting: Mapped["JobPosting"] = relationship(back_populates="repost_events")


class JobSourceSighting(Base):
    __tablename__ = "job_source_sightings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    sighting_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    publisher_name: Mapped[Optional[str]] = mapped_column(String(255))
    collection_provider: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_direct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    applicant_count: Mapped[Optional[int]] = mapped_column(Integer)
    job_posting: Mapped["JobPosting"] = relationship(back_populates="source_sightings")
    __table_args__ = (
        UniqueConstraint("job_posting_id", "sighting_key", name="uq_sightings_posting_key"),
    )


class SalaryBenchmark(Base):
    __tablename__ = "salary_benchmarks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    metro_area: Mapped[Optional[str]] = mapped_column(String(500))
    seniority: Mapped[Optional[str]] = mapped_column(String(50))
    salary_p25: Mapped[Optional[int]] = mapped_column(Integer)
    salary_p50: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_p75: Mapped[Optional[int]] = mapped_column(Integer)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    __table_args__ = (UniqueConstraint("title_normalized", "metro_area", "seniority", name="uq_salary_benchmark"),)


class LocationCache(Base):
    __tablename__ = "location_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    location_raw: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="nominatim")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    city: Mapped[Optional[str]] = mapped_column(String(200))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    metro_area: Mapped[Optional[str]] = mapped_column(String(500))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000))
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


# device_id identifies an anonymous browser (a UUID issued client-side and sent
# as a request header). JobLens has no login system, so it is the only owner
# key available for the per-user tables below.


class JobFavorite(Base):
    __tablename__ = "job_favorites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    job_posting: Mapped["JobPosting"] = relationship(lazy="selectin")
    __table_args__ = (UniqueConstraint("device_id", "job_posting_id", name="uq_job_favorites_device_job"),)


class JobApplication(Base):
    __tablename__ = "job_applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ApplicationStatus.applied.value)
    applied_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    job_posting: Mapped["JobPosting"] = relationship(lazy="selectin")
    __table_args__ = (UniqueConstraint("device_id", "job_posting_id", name="uq_job_applications_device_job"),)


class JobNote(Base):
    __tablename__ = "job_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    job_posting: Mapped["JobPosting"] = relationship(lazy="selectin")
    __table_args__ = (UniqueConstraint("device_id", "job_posting_id", name="uq_job_notes_device_job"),)


class JobView(Base):
    __tablename__ = "job_views"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    job_posting: Mapped["JobPosting"] = relationship(lazy="selectin")
    __table_args__ = (
        UniqueConstraint("device_id", "job_posting_id", name="uq_job_views_device_job"),
        Index("ix_job_views_device_viewed", "device_id", "viewed_at"),
    )


class JobDismissal(Base):
    __tablename__ = "job_dismissals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    job_posting: Mapped["JobPosting"] = relationship(lazy="selectin")
    __table_args__ = (UniqueConstraint("device_id", "job_posting_id", name="uq_job_dismissals_device_job"),)


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    __table_args__ = (UniqueConstraint("device_id", "name", name="uq_saved_searches_device_name"),)
