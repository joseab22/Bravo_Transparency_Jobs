from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SkillOut(BaseModel):
    skill: str
    skill_category: Optional[str] = None
    class Config:
        from_attributes = True


class SourceSightingOut(BaseModel):
    source: str
    source_url: Optional[str] = None
    applicant_count: Optional[int] = None
    first_seen: datetime
    last_seen: datetime
    class Config:
        from_attributes = True


class RepostEventOut(BaseModel):
    occurrence_number: int
    date_seen: datetime
    source: Optional[str] = None
    days_since_previous: Optional[int] = None
    class Config:
        from_attributes = True


class JobEventOut(BaseModel):
    id: int
    event_type: str
    timestamp: datetime
    source: Optional[str] = None
    description: Optional[str] = None
    payload: Optional[dict] = None
    class Config:
        from_attributes = True


class CompanyOut(BaseModel):
    id: int
    name: str
    industry: Optional[str] = None
    glassdoor_rating: Optional[float] = None
    ghost_job_rate: Optional[float] = None
    avg_reposts: Optional[float] = None
    median_time_to_fill: Optional[int] = None
    hiring_intensity: Optional[float] = None
    class Config:
        from_attributes = True


class JobPostingListItem(BaseModel):
    id: int
    title_normalized: str
    title_raw: str
    job_family: Optional[str] = None
    specialization: Optional[str] = None
    title_parse_confidence: Optional[float] = None
    listing_classification: str = "original"
    canonical_job_id: Optional[int] = None
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
    salary_listed: bool
    date_posted: Optional[datetime] = None
    date_first_seen: datetime
    days_active: int
    applicant_count: Optional[int] = None
    repost_count: int
    is_active: bool
    # Transparency scores
    ghost_job_probability: Optional[float] = None
    ghost_confidence: Optional[float] = None
    health_score: Optional[float] = None
    competition_score: Optional[float] = None
    interview_opportunity_score: Optional[float] = None
    salary_fairness_score: Optional[float] = None
    # Analytics
    activity_score: Optional[float] = None
    active_hiring_confidence: Optional[float] = None
    description_change_score: Optional[float] = None
    applicant_trend: Optional[float] = None
    salary_trend: Optional[float] = None
    # Relations
    source_sightings: List[SourceSightingOut] = Field(default_factory=list)
    skills: List[SkillOut] = Field(default_factory=list)
    class Config:
        from_attributes = True


class JobPostingDetail(JobPostingListItem):
    description_raw: Optional[str] = None
    education_required: Optional[str] = None
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    market_salary: Optional[int] = None
    stability_score: Optional[float] = None
    department: Optional[str] = None
    source_url: Optional[str] = None
    repost_events: List[RepostEventOut] = Field(default_factory=list)
    events: List[JobEventOut] = Field(default_factory=list)
    class Config:
        from_attributes = True


class PaginatedJobsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    results: List[JobPostingListItem]


class MarketStats(BaseModel):
    total_active_jobs: int
    avg_ghost_probability: float
    avg_health_score: float
    avg_active_hiring_confidence: float
    high_ghost_risk_count: int
    top_industries: List[dict]
    top_skills: List[dict]
    avg_days_active: float
    total_applicants: int
