"""
Core unit tests — normalizer, scoring, identity key.
Run: pytest tests/ -v
"""
import pytest
from app.services.normalizer import (
    normalize_title, extract_seniority, extract_skills,
    build_job_identity_key, normalize_location_text,
)
from app.services.scoring import ScoringService


# ---------------------------------------------------------------------------
# Title normalizer
# ---------------------------------------------------------------------------

class TestNormalizeTitle:
    def test_bi_alias(self):
        assert normalize_title("Business Intelligence Analyst") == "data analyst"
    def test_swe_alias(self):
        assert normalize_title("SWE II") == "software engineer"
    def test_ml_alias(self):
        assert normalize_title("ML Engineer") == "machine learning engineer"
    def test_output_lowercase(self):
        assert normalize_title("Data Scientist") == normalize_title("data scientist")
    def test_sde_alias(self):
        assert normalize_title("SDE") == "software engineer"


class TestExtractSeniority:
    def test_senior(self):
        assert extract_seniority("Senior Data Analyst") == "senior"
    def test_junior(self):
        assert extract_seniority("Junior Software Engineer") == "entry"
    def test_lead(self):
        assert extract_seniority("Lead Data Engineer") == "lead"
    def test_default_mid(self):
        assert extract_seniority("Data Analyst") == "mid"
    def test_sr_abbreviation(self):
        assert extract_seniority("Sr. Software Engineer") == "senior"


class TestExtractSkills:
    def test_python_sql(self):
        skills = extract_skills("Must know Python and SQL.")
        names = {s["skill"] for s in skills}
        assert "Python" in names and "SQL" in names
    def test_empty(self):
        assert extract_skills("") == []
    def test_aws_cloud_category(self):
        skills = extract_skills("Experience with AWS required.")
        cats = {s["skill"]: s["skill_category"] for s in skills}
        assert cats.get("AWS") == "Cloud"
    def test_docker_devops_category(self):
        skills = extract_skills("Docker and Kubernetes experience preferred.")
        cats = {s["skill"]: s["skill_category"] for s in skills}
        assert cats.get("Docker") == "DevOps"


class TestJobIdentityKey:
    def test_basic_key_slugs(self):
        key = build_job_identity_key("TechCorp Inc.", "data analyst", "Los Angeles")
        assert "techcorp" in key
        assert "data_analyst" in key
        assert "los_angeles" in key
    def test_no_metro(self):
        key = build_job_identity_key("Acme", "engineer", None)
        assert "acme" in key
    def test_special_chars_stripped(self):
        key = build_job_identity_key("Tech-Corp, LLC.", "data analyst", None)
        assert "." not in key


class TestLocationNorm:
    def test_la(self):
        assert normalize_location_text("la") == "Los Angeles"
    def test_sf(self):
        assert normalize_location_text("sf") == "San Francisco"
    def test_nyc(self):
        assert normalize_location_text("nyc") == "New York"
    def test_unknown_passthrough(self):
        assert normalize_location_text("Kalamazoo, MI") == "Kalamazoo, MI"


# ---------------------------------------------------------------------------
# Scoring (unit — no DB)
# ---------------------------------------------------------------------------

class FakeJob:
    def __init__(self, **kwargs):
        defaults = dict(
            repost_count=0, days_active=5, applicant_count=30,
            salary_listed=True, company=None, ghost_job_probability=0.1,
            salary_min=80000, salary_max=100000, job_identity_key="test__analyst__la",
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class TestScoringService:
    def setup_method(self):
        self.scorer = ScoringService()

    def test_health_score_in_range(self):
        score = self.scorer._health_score(FakeJob(), ghost_prob=0.1)
        assert 0 <= score <= 100

    def test_high_ghost_lowers_health(self):
        good = self.scorer._health_score(FakeJob(days_active=3, applicant_count=20, salary_listed=True), ghost_prob=0.05)
        bad  = self.scorer._health_score(FakeJob(days_active=200, applicant_count=2000, salary_listed=False), ghost_prob=0.92)
        assert good > bad

    def test_competition_high(self):
        assert self.scorer._competition_score(FakeJob(applicant_count=1500)) >= 90

    def test_competition_low(self):
        assert self.scorer._competition_score(FakeJob(applicant_count=15)) <= 30

    def test_activity_score_fresh(self):
        score = self.scorer._activity_score(FakeJob(days_active=3, repost_count=0, salary_listed=True))
        assert score > 70

    def test_activity_score_stale(self):
        score = self.scorer._activity_score(FakeJob(days_active=200, repost_count=8, salary_listed=False))
        assert score < 40
