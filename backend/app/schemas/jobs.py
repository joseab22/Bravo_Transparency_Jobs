from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SkillOut(ORMModel):
    skill: str
    skill_category: Optional[str] = None


class SourceSightingOut(ORMModel):
    source: str
    source_url: Optional[str] = None
    applicant_count: Optional[int] = None
    first_seen: datetime
    last_seen: datetime


class RepostEventOut(ORMModel):
    occurrence_number: int
    date_seen: datetime
    source: Optional[str] = None
    days_since_previous: Optional[int] = None


class JobEventOut(ORMModel):
    id: int
    event_type: str
    timestamp: datetime
    source: Optional[str] = None
    description: Optional[str] = None
    payload: Optional[dict] = None


class CompanyOut(ORMModel):
    id: int
    name: str
    industry: Optional[str] = None
    glassdoor_rating: Optional[float] = None
    ghost_job_rate: Optional[float] = None
    avg_reposts: Optional[float] = None
    median_time_to_fill: Optional[int] = None
    hiring_intensity: Optional[float] = None


class JobPostingListItem(ORMModel):
    id: int
    source: str
    source_url: Optional[str] = None
    external_id: Optional[str] = None
    title_raw: str
    title_normalized: str
    job_family: Optional[str] = None
    specialization: Optional[str] = None
    title_parse_confidence: Optional[float] = None
    company: CompanyOut
    location_raw: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    metro_area: Optional[str] = None
    remote_type: Optional[str] = None
    seniority: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    salary_listed: bool
    date_posted: Optional[datetime] = None
    date_first_seen: datetime
    date_last_seen: datetime
    days_active: int
    applicant_count: Optional[int] = None
    listing_classification: str = "original"
    canonical_job_id: Optional[int] = None
    repost_count: int
    is_active: bool
    ghost_job_probability: Optional[float] = None
    ghost_confidence: Optional[float] = None
    health_score: Optional[float] = None
    active_hiring_confidence: Optional[float] = None
    competition_score: Optional[float] = None
    interview_opportunity_score: Optional[float] = None
    salary_fairness_score: Optional[float] = None
    activity_score: Optional[float] = None
    description_change_score: Optional[float] = None
    applicant_trend: Optional[float] = None
    salary_trend: Optional[float] = None
    source_sightings: list[SourceSightingOut] = Field(default_factory=list)
    skills: list[SkillOut] = Field(default_factory=list)


class JobPostingDetail(JobPostingListItem):
    description_raw: Optional[str] = None
    education_required: Optional[str] = None
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    market_salary: Optional[int] = None
    stability_score: Optional[float] = None
    department: Optional[str] = None
    repost_events: list[RepostEventOut] = Field(default_factory=list)
    events: list[JobEventOut] = Field(default_factory=list)


class PaginatedJobsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    results: list[JobPostingListItem]


class MarketStats(BaseModel):
    total_active_jobs: int
    scored_active_jobs: int
    avg_active_hiring_confidence: float
    avg_ghost_probability: float
    avg_health_score: float
    high_ghost_risk_count: int
    classification_counts: list[dict]
    top_industries: list[dict]
    top_skills: list[dict]
    avg_days_active: float
    total_applicants: int
