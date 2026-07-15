from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
KNOWN_SOURCES = {
    "simplify", "jsearch", "indeed", "linkedin", "glassdoor", "ziprecruiter",
    "dice", "monster", "jobright",
}


class Settings(BaseSettings):
    """Runtime settings loaded from backend/.env when present."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    env: str = "development"
    secret_key: str = "dev-secret-key"
    api_prefix: str = "/api/v1"
    debug: bool = False
    cors_origins: str = "http://localhost:3000"
    admin_api_key: str = ""

    # Database / queue
    database_url: str = "postgresql+asyncpg://joblens:joblens_dev@localhost:5432/joblens"
    redis_url: str = "redis://localhost:6379/0"

    # Collection
    enabled_scraper_sources: str = "simplify"
    max_pages_per_source: int = Field(default=1, ge=1, le=100)

    # JSearch Pro plan controls. The scheduled generic collection uses seven
    # role queries, ten pages per query, and runs daily: at most 2,170
    # scheduled calls in a 31-day month before retries. A Redis-backed
    # hard budget stops all JSearch-backed adapters at 9,000 attempts by
    # default, leaving 1,000 requests for manual tests and provider variance.
    jsearch_pages_per_query: int = Field(default=10, ge=1, le=20)
    jsearch_schedule_every_hours: int = Field(default=24, ge=1, le=24)
    jsearch_monthly_request_limit: int = Field(default=10_000, ge=1, le=1_000_000)
    jsearch_request_reserve: int = Field(default=1_000, ge=1, le=999_999)
    jsearch_queries: str = (
        "software engineer,data analyst,data engineer,data scientist,"
        "machine learning engineer,product manager,security engineer"
    )
    jsearch_country: str = "us"
    jsearch_language: str = "en"
    jsearch_location: str = "United States"
    jsearch_excluded_publishers: str = "simplify,simplifyjobs,simplify jobs"
    jsearch_excluded_domains: str = "simplify.jobs"
    allow_overlapping_jsearch_sources: bool = False
    ingest_batch_size: int = Field(default=250, ge=1, le=5000)
    snapshot_min_interval_hours: int = Field(default=24, ge=0, le=720)
    scrape_lock_seconds: int = Field(default=43_200, ge=300, le=172_800)
    auto_expire_stale_jobs: bool = False
    stale_job_days: int = Field(default=14, ge=1, le=365)

    # Identity / history
    parallel_listing_window_days: int = Field(default=2, ge=0, le=14)
    repost_min_gap_days: int = Field(default=7, ge=1, le=90)
    candidate_history_days: int = Field(default=365, ge=30, le=1825)

    # Source credentials
    openwebninja_api_key: str = ""
    rapidapi_key: str = ""
    jsearch_date_posted: str = "month"
    linkedin_scraper_mode: str = "jsearch"
    ziprecruiter_api_key: str = ""
    dice_api_key: str = ""
    jobright_api_key: str = ""
    jobright_api_base_url: str = "https://api.jobright.ai/v1"

    # Public Simplify feeds. Kept configurable because repository paths can change.
    simplify_new_grad_feed_url: str = (
        "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/"
        "dev/.github/scripts/listings.json"
    )
    simplify_internship_feed_url: str = (
        "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/"
        "dev/.github/scripts/listings.json"
    )
    simplify_max_records: int = Field(default=50_000, ge=100, le=100_000)

    # Optional location enrichment. Disabled by default so collection never
    # makes one geocoding request per job.
    geocoding_enabled: bool = False
    geocoding_provider: str = "nominatim"
    geocoding_batch_size: int = Field(default=20, ge=1, le=500)
    geocoding_delay_seconds: float = Field(default=1.1, ge=0.0, le=30.0)
    geocoding_retry_hours: int = Field(default=24, ge=1, le=720)
    google_geocoding_api_key: str = ""
    location_cluster_radius_miles: float = Field(default=40.0, ge=1.0, le=500.0)

    # Scoring weights
    ghost_job_repost_weight: float = 0.30
    ghost_job_days_active_weight: float = 0.25
    ghost_job_applicants_weight: float = 0.15
    ghost_job_salary_weight: float = 0.10
    ghost_job_rating_weight: float = 0.10
    ghost_job_history_weight: float = 0.10
    scoring_batch_size: int = Field(default=1000, ge=1, le=10_000)

    # NLP / embeddings. Expensive description embeddings are a separate task.
    embedding_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    description_similarity_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    semantic_title_matching_enabled: bool = False
    identity_candidate_limit: int = Field(default=100, ge=10, le=1000)
    description_embeddings_enabled: bool = False
    embedding_batch_size: int = Field(default=100, ge=1, le=1000)

    @property
    def jsearch_query_list(self) -> list[str]:
        return [value.strip() for value in self.jsearch_queries.split(",") if value.strip()]

    @property
    def jsearch_excluded_publisher_set(self) -> set[str]:
        return {value.strip().lower() for value in self.jsearch_excluded_publishers.split(",") if value.strip()}

    @property
    def jsearch_excluded_domain_set(self) -> set[str]:
        return {value.strip().lower().removeprefix("www.") for value in self.jsearch_excluded_domains.split(",") if value.strip()}

    @property
    def jsearch_application_budget(self) -> int:
        return self.jsearch_monthly_request_limit - self.jsearch_request_reserve

    @property
    def jsearch_requests_per_run(self) -> int:
        return len(self.jsearch_query_list) * self.jsearch_pages_per_query

    @property
    def jsearch_estimated_monthly_requests(self) -> int:
        runs_per_day = 24 // self.jsearch_schedule_every_hours
        return self.jsearch_requests_per_run * runs_per_day * 31

    @property
    def enabled_source_set(self) -> set[str]:
        return {
            value.strip().lower()
            for value in self.enabled_scraper_sources.split(",")
            if value.strip()
        }

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        total = sum(
            (
                self.ghost_job_repost_weight,
                self.ghost_job_days_active_weight,
                self.ghost_job_applicants_weight,
                self.ghost_job_salary_weight,
                self.ghost_job_rating_weight,
                self.ghost_job_history_weight,
            )
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError("Ghost-job scoring weights must sum to 1.0")

        unknown = self.enabled_source_set - KNOWN_SOURCES
        if unknown:
            raise ValueError(f"Unknown ENABLED_SCRAPER_SOURCES values: {sorted(unknown)}")

        if not self.jsearch_query_list:
            raise ValueError("JSEARCH_QUERIES must contain at least one query")
        if self.jsearch_request_reserve >= self.jsearch_monthly_request_limit:
            raise ValueError("JSEARCH_REQUEST_RESERVE must be below JSEARCH_MONTHLY_REQUEST_LIMIT")
        if 24 % self.jsearch_schedule_every_hours != 0:
            raise ValueError("JSEARCH_SCHEDULE_EVERY_HOURS must divide evenly into 24")
        if self.jsearch_estimated_monthly_requests > self.jsearch_application_budget:
            raise ValueError(
                "Scheduled JSearch usage exceeds the protected application budget: "
                f"{self.jsearch_estimated_monthly_requests} > {self.jsearch_application_budget}"
            )
        overlapping = self.enabled_source_set & {"linkedin", "indeed"}
        if "jsearch" in self.enabled_source_set and overlapping and not self.allow_overlapping_jsearch_sources:
            raise ValueError(
                "Enable generic jsearch OR the targeted linkedin/indeed adapters, not both. "
                "Set ALLOW_OVERLAPPING_JSEARCH_SOURCES=true only when duplicate searches are intentional."
            )

        provider = self.geocoding_provider.lower().strip()
        if provider not in {"nominatim", "google"}:
            raise ValueError("GEOCODING_PROVIDER must be 'nominatim' or 'google'")
        self.geocoding_provider = provider
        if self.geocoding_enabled and provider == "google" and not self.google_geocoding_api_key:
            raise ValueError("GOOGLE_GEOCODING_API_KEY is required when GEOCODING_PROVIDER=google")

        if self.env.lower() == "production" and self.secret_key in {
            "", "dev-secret-key", "change-me",
        }:
            raise ValueError("A strong SECRET_KEY is required in production")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
