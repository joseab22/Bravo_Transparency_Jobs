from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    env: str = "development"
    secret_key: str = ""
    api_prefix: str = "/api/v1"
    debug: bool = True

    # Database
    database_url: str = ""

    # Redis
    redis_url: str = ""

    # Scraping behavior
    scrape_interval_hours: int = 6
    max_pages_per_source: int = 10

    # --- Source API keys ---
    # Shared RapidAPI key (used by Indeed, LinkedIn jsearch mode, Glassdoor, Monster)
    rapidapi_key: str = ""

    # LinkedIn
    linkedin_scraper_mode: str = "jsearch"   # jsearch | playwright | api
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    # Glassdoor
    glassdoor_partner_id: str = ""
    glassdoor_partner_key: str = ""

    # ZipRecruiter
    ziprecruiter_api_key: str = ""

    # Dice
    dice_api_key: str = ""

    # Monster
    monster_api_key: str = ""

    # Jobright
    jobright_api_key: str = ""
    jobright_api_base_url: str = "https://api.jobright.ai/v1"

    # Simplify
    simplify_api_key: str = ""   # optional; defaults to public GitHub feed

    # Location
    google_geocoding_api_key: str = ""
    location_cluster_radius_miles: float = 40.0

    # Ghost job scoring weights
    ghost_job_repost_weight: float = 0.30
    ghost_job_days_active_weight: float = 0.25
    ghost_job_applicants_weight: float = 0.15
    ghost_job_salary_weight: float = 0.10
    ghost_job_rating_weight: float = 0.10
    ghost_job_history_weight: float = 0.10

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.85

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
