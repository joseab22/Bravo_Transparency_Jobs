from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db.session import Base
import enum


# =============================================================================
# Enums
# =============================================================================

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
    company_site = "company_site"


class EventType(str, enum.Enum):
    created = "created"
    reposted = "reposted"
    applicant_spike = "applicant_spike"
    salary_changed = "salary_changed"
    title_changed = "title_changed"
    description_changed = "description_changed"
    expired = "expired"
    reactivated = "reactivated"
    source_added = "source_added"
    ghost_flagged = "ghost_flagged"


# =============================================================================
# Company
# =============================================================================

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    glassdoor_rating: Mapped[Optional[float]] = mapped_column(Float)  # company_rating per spec
    glassdoor_url: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Derived metrics updated by scoring worker
    turnover_score: Mapped[Optional[float]] = mapped_column(Float)
    hiring_intensity: Mapped[Optional[float]] = mapped_column(Float)
    ghost_job_rate: Mapped[Optional[float]] = mapped_column(Float)
    avg_reposts: Mapped[Optional[float]] = mapped_column(Float)
    median_time_to_fill: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job_postings: Mapped[List["JobPosting"]] = relationship(back_populates="company", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("name_normalized", name="uq_companies_name_normalized"),
    )


# =============================================================================
# Job Posting — core record
# =============================================================================

class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)

    # Identity
    job_identity_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    identity_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    canonical_job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    listing_classification: Mapped[str] = mapped_column(
        String(30), default="original", nullable=False, index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(SAEnum(JobSource), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))

    # Titles
    title_raw: Mapped[str] = mapped_column(String(500), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    job_family: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    specialization: Mapped[Optional[str]] = mapped_column(String(300))
    title_parse_confidence: Mapped[Optional[float]] = mapped_column(Float)

    # Location (spec: city, state, country, metro, lat, lon)
    location_raw: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[Optional[str]] = mapped_column(String(200))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100), default="US")
    metro_area: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    remote_type: Mapped[Optional[str]] = mapped_column(SAEnum(RemoteType))

    # Classification
    seniority: Mapped[Optional[str]] = mapped_column(SAEnum(SeniorityLevel))
    employment_type: Mapped[Optional[str]] = mapped_column(SAEnum(EmploymentType))
    department: Mapped[Optional[str]] = mapped_column(String(200))
    industry: Mapped[Optional[str]] = mapped_column(String(200))

    # Compensation
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD")
    salary_listed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Requirements
    education_required: Mapped[Optional[str]] = mapped_column(String(200))
    experience_years_min: Mapped[Optional[int]] = mapped_column(Integer)
    experience_years_max: Mapped[Optional[int]] = mapped_column(Integer)

    # Description stored on posting; embedding in separate table
    description_raw: Mapped[Optional[str]] = mapped_column(Text)

    # Activity timestamps
    date_posted: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    date_first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    date_last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    days_active: Mapped[int] = mapped_column(Integer, default=0)

    # Applicant tracking
    applicant_count: Mapped[Optional[int]] = mapped_column(Integer)

    # --- Transparency / analytics scores (spec §Analytics Requirements) ---
    ghost_job_probability: Mapped[Optional[float]] = mapped_column(Float)
    ghost_confidence: Mapped[Optional[float]] = mapped_column(Float)          # confidence_score
    health_score: Mapped[Optional[float]] = mapped_column(Float)
    competition_score: Mapped[Optional[float]] = mapped_column(Float)
    interview_opportunity_score: Mapped[Optional[float]] = mapped_column(Float)
    salary_fairness_score: Mapped[Optional[float]] = mapped_column(Float)
    market_salary: Mapped[Optional[int]] = mapped_column(Integer)
    stability_score: Mapped[Optional[float]] = mapped_column(Float)

    # Analytics fields required by spec
    activity_score: Mapped[Optional[float]] = mapped_column(Float)              # hiring activity signal
    active_hiring_confidence: Mapped[Optional[float]] = mapped_column(Float)    # 0-100 confidence role is actively hiring
    description_change_score: Mapped[Optional[float]] = mapped_column(Float)   # how much desc has drifted
    applicant_trend: Mapped[Optional[float]] = mapped_column(Float)            # slope of applicant growth
    salary_trend: Mapped[Optional[float]] = mapped_column(Float)               # salary change direction

    # Repost tracking
    repost_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="job_postings", lazy="selectin")
    skills: Mapped[List["JobSkill"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    snapshots: Mapped[List["JobSnapshot"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    repost_events: Mapped[List["RepostEvent"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    source_sightings: Mapped[List["JobSourceSighting"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    events: Mapped[List["JobEvent"]] = relationship(back_populates="job_posting", cascade="all, delete-orphan", lazy="selectin")
    embedding: Mapped[Optional["JobEmbedding"]] = relationship(back_populates="job_posting", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_job_postings_identity_active", "job_identity_key", "is_active"),
        Index("ix_job_postings_fingerprint_active", "identity_fingerprint", "is_active"),
        Index("ix_job_postings_source_external", "source", "external_id"),
    )


# =============================================================================
# Job Snapshot — point-in-time record of mutable fields (spec §Snapshots)
# =============================================================================

class JobSnapshot(Base):
    __tablename__ = "job_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)

    # spec fields: snapshot_id, job_id, source, applicants, description, salary, date_seen
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)  # date_seen
    source: Mapped[Optional[str]] = mapped_column(SAEnum(JobSource))            # which platform this snapshot came from
    applicant_count: Mapped[Optional[int]] = mapped_column(Integer)             # applicants
    description_raw: Mapped[Optional[str]] = mapped_column(Text)               # description at this point in time
    description_hash: Mapped[Optional[str]] = mapped_column(String(64))        # sha256 for change detection
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)                 # salary (min)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)                 # salary (max)
    title_raw: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="snapshots")


# =============================================================================
# Job Event — audit log of all state changes (spec §Events)
# =============================================================================

class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)    # event_id
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)  # job_id
    event_type: Mapped[str] = mapped_column(SAEnum(EventType), nullable=False)  # event_type
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)  # timestamp
    source: Mapped[Optional[str]] = mapped_column(SAEnum(JobSource))
    payload: Mapped[Optional[dict]] = mapped_column(JSON)  # arbitrary event metadata
    description: Mapped[Optional[str]] = mapped_column(String(500))

    job_posting: Mapped["JobPosting"] = relationship(back_populates="events")


# =============================================================================
# Job Embedding — standalone table for pgvector (spec §Embeddings)
# =============================================================================

class JobEmbedding(Base):
    __tablename__ = "job_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)                 # embedding_id
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, unique=True)  # job_id
    vector: Mapped[List[float]] = mapped_column(Vector(384), nullable=False)   # vector (384-dim MiniLM)
    model_name: Mapped[str] = mapped_column(String(200), default="all-MiniLM-L6-v2")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="embedding")

    __table_args__ = (
        Index("ix_job_embeddings_vector", "vector", postgresql_using="ivfflat",
              postgresql_with={"lists": 100}),
    )


# =============================================================================
# Job Skills
# =============================================================================

class JobSkill(Base):
    __tablename__ = "job_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    skill: Mapped[str] = mapped_column(String(200), nullable=False)
    skill_normalized: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    skill_category: Mapped[Optional[str]] = mapped_column(String(100))

    job_posting: Mapped["JobPosting"] = relationship(back_populates="skills")

    __table_args__ = (
        UniqueConstraint("job_posting_id", "skill_normalized", name="uq_job_skills_posting_skill"),
    )


# =============================================================================
# Repost Events
# =============================================================================

class RepostEvent(Base):
    __tablename__ = "repost_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    job_identity_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    occurrence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(SAEnum(JobSource))
    days_since_previous: Mapped[Optional[int]] = mapped_column(Integer)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="repost_events")


# =============================================================================
# Source Sightings — cross-platform tracking
# =============================================================================

class JobSourceSighting(Base):
    __tablename__ = "job_source_sightings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(SAEnum(JobSource), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    applicant_count: Mapped[Optional[int]] = mapped_column(Integer)

    job_posting: Mapped["JobPosting"] = relationship(back_populates="source_sightings")

    __table_args__ = (
        UniqueConstraint("job_posting_id", "source", name="uq_sightings_posting_source"),
    )


# =============================================================================
# Salary Benchmarks
# =============================================================================

class SalaryBenchmark(Base):
    __tablename__ = "salary_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    metro_area: Mapped[Optional[str]] = mapped_column(String(200))
    seniority: Mapped[Optional[str]] = mapped_column(SAEnum(SeniorityLevel))
    salary_p25: Mapped[Optional[int]] = mapped_column(Integer)
    salary_p50: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_p75: Mapped[Optional[int]] = mapped_column(Integer)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("title_normalized", "metro_area", "seniority", name="uq_salary_benchmark"),
    )
